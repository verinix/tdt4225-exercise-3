import ast
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from DbConnector import DbConnector

DATASET_PATH = Path(__file__).parent / "data"
BATCH_SIZE = 1000

def find_duplicate_ids(path):
    seen_ids = set()
    duplicate_ids = set()

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                movie_id = int(row["id"])
            except ValueError:
                continue

            if movie_id in seen_ids:
                duplicate_ids.add(movie_id)
            seen_ids.add(movie_id)

    return duplicate_ids

def classify_duplicate_ids(path, duplicate_ids):
    records_by_id = defaultdict(list)

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                movie_id = int(row["id"])
            except ValueError:
                continue

            if movie_id in duplicate_ids:
                records_by_id[movie_id].append(row)

    identical_ids = set()
    conflicting_ids = set()

    for movie_id, records in records_by_id.items():
        first_record = records[0]
        identical = True

        for record in records[1:]:
            if record != first_record:
                identical = False
                break

        if identical:
            identical_ids.add(movie_id)
        else:
            conflicting_ids.add(movie_id)

    return identical_ids, conflicting_ids

def is_missing(value):
    return value is None or value.strip().lower() in ("", "null", "none", "nan")

def parse_text(value):
    return None if is_missing(value) else value

def parse_optional_int(value):
    return None if is_missing(value) else int(float(value))

def parse_optional_float(value):
    return None if is_missing(value) else float(value)

def parse_positive_int(value):
    number = parse_optional_int(value)
    return number if number is not None and number > 0 else None

def parse_positive_float(value):
    number = parse_optional_float(value)
    return number if number is not None and number > 0 else None

def parse_object(value):
    return None if is_missing(value) else ast.literal_eval(value)

def parse_objects(value):
    return [] if is_missing(value) else ast.literal_eval(value)

def parse_date(value):
    return None if is_missing(value) else datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)

def find_credits(conflicting_ids):
    credits_by_movie = {}

    with (DATASET_PATH / "credits.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = int(row["id"])
            if movie_id in conflicting_ids:
                continue

            cast = parse_objects(row["cast"])
            cast.sort(key=lambda person: person["order"])
            crew = parse_objects(row["crew"])
            credits_by_movie[movie_id] = (cast, crew)

    return credits_by_movie

def find_keywords(conflicting_ids):
    keywords_by_movie = {}

    with (DATASET_PATH / "keywords.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = int(row["id"])
            if movie_id in conflicting_ids:
                continue

            keywords = []
            for keyword in parse_objects(row["keywords"]):
                name = keyword.get("name")
                if isinstance(name, str) and name.strip():
                    keywords.append(keyword)

            keywords_by_movie[movie_id] = keywords

    return keywords_by_movie

def find_links():
    links_by_movie = {}

    with (DATASET_PATH / "links.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            links_by_movie[int(row["movieId"])] = parse_optional_int(row["tmdbId"])

    return links_by_movie

def recreate_collections(db):
    db.drop_collection("movies")
    db.drop_collection("ratings")

def load_movies(db, conflicting_ids, credits_by_movie, keywords_by_movie):
    seen_ids = set()
    batch = []
    inserted = 0

    with (DATASET_PATH / "movies_metadata.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                movie_id = int(row["id"])
            except ValueError:
                continue

            if movie_id <= 0 or movie_id in conflicting_ids or movie_id in seen_ids:
                continue
            seen_ids.add(movie_id)

            cast, crew = credits_by_movie.get(movie_id, ([], []))

            batch.append({
                "_id": movie_id,
                "title": parse_text(row["title"]),
                "original_language": parse_text(row["original_language"]),
                "overview": parse_text(row["overview"]),
                "tagline": parse_text(row["tagline"]),
                "release_date": parse_date(row["release_date"]),
                "budget": parse_positive_int(row["budget"]),
                "revenue": parse_positive_int(row["revenue"]),
                "runtime": parse_positive_float(row["runtime"]),
                "vote_average": parse_optional_float(row["vote_average"]),
                "vote_count": parse_optional_int(row["vote_count"]),
                "genres": parse_objects(row["genres"]),
                "production_companies": parse_objects(row["production_companies"]),
                "production_countries": parse_objects(row["production_countries"]),
                "belongs_to_collection": parse_object(row["belongs_to_collection"]),
                "cast": cast,
                "crew": crew,
                "keywords": keywords_by_movie.get(movie_id, [])
            })

            if len(batch) >= BATCH_SIZE:
                db.movies.insert_many(batch)
                inserted += len(batch)
                batch = []

    if batch:
        db.movies.insert_many(batch)
        inserted += len(batch)

    print(f"Movies inserted: {inserted:,}")

def load_ratings(db, links):
    batch = []
    inserted = 0

    with (DATASET_PATH / "ratings.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = int(row["movieId"])
            batch.append({
                "user_id": int(row["userId"]),
                "movielens_id": movie_id,
                "tmdb_id": links.get(movie_id),
                "rating": float(row["rating"]),
                "timestamp": datetime.fromtimestamp(int(row["timestamp"]), timezone.utc)
            })

            if len(batch) >= BATCH_SIZE:
                db.ratings.insert_many(batch)
                inserted += len(batch)
                batch = []

    if batch:
        db.ratings.insert_many(batch)
        inserted += len(batch)

    print(f"Ratings inserted: {inserted:,}")

def create_secondary_index(db):
    db.movies.create_index([("overview", "text"), ("tagline", "text")])

def main():
    conflicting_ids = set()

    print("Duplicate cleaning")
    for filename in ("movies_metadata.csv", "credits.csv", "keywords.csv"):
        path = DATASET_PATH / filename
        duplicate_ids = find_duplicate_ids(path)
        identical_ids, conflicts = classify_duplicate_ids(path, duplicate_ids)
        conflicting_ids.update(conflicts)
        print(f"{filename}: {len(duplicate_ids):,} duplicated, {len(identical_ids):,} identical, {len(conflicts):,} conflicting IDs")

    print(f"Excluded movie IDs: {len(conflicting_ids):,}")

    credits_by_movie = find_credits(conflicting_ids)
    keywords_by_movie = find_keywords(conflicting_ids)
    links_by_movie = find_links()

    database = DbConnector()

    try:
        recreate_collections(database.db)
        load_movies(database.db, conflicting_ids, credits_by_movie, keywords_by_movie)
        load_ratings(database.db, links_by_movie)
        create_secondary_index(database.db)
    finally:
        database.close_connection()

if __name__ == "__main__":
    main()
