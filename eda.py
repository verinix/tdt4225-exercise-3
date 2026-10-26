import ast
import csv
from collections import Counter
from pathlib import Path
from statistics import median
from datetime import datetime
from math import isfinite

DATASET_PATH = Path(__file__).parent / "data"

def parse_objects(value):
    objects = ast.literal_eval(value)
    if not isinstance(objects, list) or any(not isinstance(obj, dict) for obj in objects):
        raise ValueError("Expected a list of objects")
    return objects

def classify_duplicates(path, duplicate_ids):
    original_rows = {}
    conflicting_ids = set()

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                movie_id = int(row["id"])
            except (ValueError, TypeError):
                continue

            if movie_id not in duplicate_ids:
                continue

            if movie_id in original_rows:
                if row != original_rows[movie_id]:
                    conflicting_ids.add(movie_id)
            else:
                original_rows[movie_id] = row

    return len(duplicate_ids) - len(conflicting_ids), len(conflicting_ids)

def is_missing(value):
    return value is None or value.strip().lower() in ("", "null", "none", "nan")

def analyze_credits():
    rows = 0
    invalid_movie_ids = 0
    seen_ids = set()
    duplicate_ids = set()
    malformed_rows = 0

    cast_sizes = []
    crew_sizes = []
    gender_counts = Counter()
    movies_without_director = 0
    movies_with_multiple_directors = 0
    movies_with_repeated_actors = 0
    movies_with_repeated_orders = 0

    with (DATASET_PATH / "credits.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows += 1

            try:
                movie_id = int(row["id"])
                if movie_id <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                invalid_movie_ids += 1
            else:
                if movie_id in seen_ids:
                    duplicate_ids.add(movie_id)
                seen_ids.add(movie_id)

            try:
                cast = parse_objects(row["cast"])
                crew = parse_objects(row["crew"])
            except (ValueError, SyntaxError, TypeError):
                malformed_rows += 1
                continue

            cast_sizes.append(len(cast))
            crew_sizes.append(len(crew))

            for person in cast:
                gender_counts[person["gender"]] += 1

            directors = {person["id"] for person in crew if person.get("job") == "Director"}
            if not directors:
                movies_without_director += 1
            if len(directors) > 1:
                movies_with_multiple_directors += 1
            if len({person["id"] for person in cast}) != len(cast):
                movies_with_repeated_actors += 1
            if len({person["order"] for person in cast}) != len(cast):
                movies_with_repeated_orders += 1

    print("Credits")
    print(f"Rows: {rows:,}")
    print(f"Distinct movie IDs: {len(seen_ids):,}")
    print(f"Invalid movie IDs: {invalid_movie_ids:,}")
    print(f"Duplicated movie IDs: {len(duplicate_ids):,}")
    print(f"Malformed cast/crew rows: {malformed_rows:,}")

    if duplicate_ids:
        identical, conflicting = classify_duplicates(DATASET_PATH / "credits.csv", duplicate_ids)
        print(f"Identical duplicates: {identical:,}")
        print(f"Conflicting duplicates: {conflicting:,}")

    print("\nCast and crew")
    for label, sizes in (("Cast", cast_sizes), ("Crew", crew_sizes)):
        if sizes:
            print(
                f"{label}: empty={sizes.count(0):,}, "
                f"mean={sum(sizes) / len(sizes):.2f}, "
                f"median={median(sizes):g}, max={max(sizes):,}"
            )

    print(f"Movies without a director: {movies_without_director:,}")
    print(f"Movies with multiple directors: {movies_with_multiple_directors:,}")
    print(f"Movies with repeated cast person IDs: {movies_with_repeated_actors:,}")
    print(f"Movies with repeated cast orders: {movies_with_repeated_orders:,}")

    print("\nCast gender values")
    for gender, count in sorted(gender_counts.items()):
        print(f"{gender}: {count:,}")

    return seen_ids

def analyze_keywords():
    rows = 0
    invalid_movie_ids = 0
    seen_ids = set()
    duplicate_ids = set()
    malformed_rows = 0

    empty_keyword_lists = 0
    max_keyword_count = 0
    missing_keyword_names = 0

    with (DATASET_PATH / "keywords.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows += 1

            try:
                movie_id = int(row["id"])
                if movie_id <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                invalid_movie_ids += 1
            else:
                if movie_id in seen_ids:
                    duplicate_ids.add(movie_id)
                seen_ids.add(movie_id)

            try:
                keywords = parse_objects(row["keywords"])
            except (ValueError, SyntaxError, TypeError):
                malformed_rows += 1
                continue

            if not keywords:
                empty_keyword_lists += 1

            max_keyword_count = max(max_keyword_count, len(keywords))

            for keyword in keywords:
                name = keyword.get("name")
                if not isinstance(name, str) or not name.strip():
                    missing_keyword_names += 1

    print("\nKeywords")
    print(f"Rows: {rows:,}")
    print(f"Distinct movie IDs: {len(seen_ids):,}")
    print(f"Invalid movie IDs: {invalid_movie_ids:,}")
    print(f"Duplicated movie IDs: {len(duplicate_ids):,}")
    print(f"Malformed keyword rows: {malformed_rows:,}")

    if duplicate_ids:
        identical, conflicting = classify_duplicates(DATASET_PATH / "keywords.csv", duplicate_ids)
        print(f"Identical duplicates: {identical:,}")
        print(f"Conflicting duplicates: {conflicting:,}")

    print("\nKeyword counts")
    print(f"Empty lists: {empty_keyword_lists:,}")
    print(f"Maximum: {max_keyword_count:,}")

    print(f"Invalid/missing keyword names: {missing_keyword_names:,}")

    return seen_ids

def analyze_links():
    rows = 0
    invalid_movie_ids = 0

    missing_tmdb_ids = 0
    invalid_tmdb_ids = 0

    tmdb_to_movie = {}
    movie_to_tmdb = {}
    shared_tmdb_ids = set()

    with (DATASET_PATH / "links.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows += 1

            try:
                movie_id = int(row["movieId"])
                if movie_id <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                invalid_movie_ids += 1
                continue

            movie_to_tmdb[movie_id] = None
            raw_tmdb_id = row["tmdbId"].strip()
            if not raw_tmdb_id:
                missing_tmdb_ids += 1
                continue

            try:
                number = float(raw_tmdb_id)
                if number <= 0 or not number.is_integer():
                    raise ValueError
                tmdb_id = int(number)
            except (ValueError, OverflowError):
                invalid_tmdb_ids += 1
                continue

            movie_to_tmdb[movie_id] = tmdb_id
            if tmdb_id in tmdb_to_movie:
                if tmdb_to_movie[tmdb_id] != movie_id:
                    shared_tmdb_ids.add(tmdb_id)
            else:
                tmdb_to_movie[tmdb_id] = movie_id

    print("\nLinks")
    print(f"Rows: {rows:,}")
    print(f"Distinct MovieLens IDs: {len(movie_to_tmdb):,}")
    print(f"Invalid MovieLens IDs: {invalid_movie_ids:,}")
    print(f"Missing TMDB IDs: {missing_tmdb_ids:,}")
    print(f"Invalid TMDB IDs: {invalid_tmdb_ids:,}")
    print(f"Distinct mapped TMDB IDs: {len(tmdb_to_movie):,}")
    print(f"TMDB IDs shared by multiple MovieLens IDs: {len(shared_tmdb_ids):,}")

    return movie_to_tmdb

def analyze_metadata():
    rows = 0
    invalid_movie_ids = 0
    seen_ids = set()
    duplicate_ids = set()

    missing_text = Counter()
    missing_dates = 0
    invalid_dates = 0
    decades = Counter()

    numeric_fields = ("budget", "revenue", "runtime", "vote_average", "vote_count")
    numeric_counts = {field: Counter() for field in numeric_fields}
    positive_revenues = []
    positive_runtimes = []

    nested_fields = ("genres", "production_companies", "production_countries")
    nested_counts = {field: Counter() for field in nested_fields}
    collections = Counter()

    with (DATASET_PATH / "movies_metadata.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows += 1

            try:
                movie_id = int(row["id"])
                if movie_id <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                invalid_movie_ids += 1
                continue

            if movie_id in seen_ids:
                duplicate_ids.add(movie_id)
            seen_ids.add(movie_id)

            for field in ("title", "original_language", "overview", "tagline"):
                if is_missing(row[field]):
                    missing_text[field] += 1

            if is_missing(row["release_date"]):
                missing_dates += 1
            else:
                try:
                    release_date = datetime.strptime(row["release_date"], "%Y-%m-%d")
                    decades[release_date.year // 10 * 10] += 1
                except ValueError:
                    invalid_dates += 1

            for field in numeric_fields:
                value = row[field]

                if is_missing(value):
                    numeric_counts[field]["missing"] += 1
                    continue

                try:
                    number = float(value)
                except (ValueError, TypeError):
                    numeric_counts[field]["invalid"] += 1
                    continue

                if (
                    not isfinite(number)
                    or number < 0
                    or (field == "vote_average" and number > 10)
                    or (field == "vote_count" and not number.is_integer())
                ):
                    numeric_counts[field]["invalid"] += 1
                elif number == 0:
                    numeric_counts[field]["zero"] += 1
                else:
                    numeric_counts[field]["positive"] += 1
                    if field == "revenue":
                        positive_revenues.append(number)
                    elif field == "runtime":
                        positive_runtimes.append(number)

            for field in nested_fields:
                value = row[field]

                if is_missing(value):
                    nested_counts[field]["missing"] += 1
                    continue

                try:
                    objects = parse_objects(value)
                except (ValueError, SyntaxError, TypeError):
                    nested_counts[field]["malformed"] += 1
                    continue

                if not objects:
                    nested_counts[field]["empty"] += 1

            value = row["belongs_to_collection"]
            if is_missing(value):
                collections["missing"] += 1
            else:
                try:
                    collection = ast.literal_eval(value)
                    if not isinstance(collection, dict):
                        raise ValueError
                    collections["present"] += 1
                except (ValueError, SyntaxError, TypeError):
                    collections["malformed"] += 1

    print("\nMovie metadata")
    print(f"Rows: {rows:,}")
    print(f"Distinct movie IDs: {len(seen_ids):,}")
    print(f"Invalid movie IDs: {invalid_movie_ids:,}")
    print(f"Duplicated movie IDs: {len(duplicate_ids):,}")

    if duplicate_ids:
        identical, conflicting = classify_duplicates(DATASET_PATH / "movies_metadata.csv", duplicate_ids)
        print(f"Identical duplicates: {identical:,}")
        print(f"Conflicting duplicates: {conflicting:,}")

    print("\nMissing text fields")
    for field, count in missing_text.items():
        print(f"{field}: {count:,}")

    print(f"\nMissing release dates: {missing_dates:,}")
    print(f"Invalid release dates: {invalid_dates:,}")

    print("\nNumeric fields")
    for field, counts in numeric_counts.items():
        print(
            f"{field}: missing={counts['missing']:,}, "
            f"zero={counts['zero']:,}, "
            f"invalid={counts['invalid']:,}, "
            f"positive={counts['positive']:,}"
        )

    if positive_revenues:
        print(f"Median positive revenue: ${median(positive_revenues):,.0f}")
    if positive_runtimes:
        print(f"Median positive runtime: {median(positive_runtimes):.1f} minutes")

    print("\nNested fields")
    for field, counts in nested_counts.items():
        print(
            f"{field}: missing={counts['missing']:,}, "
            f"empty={counts['empty']:,}, "
            f"malformed={counts['malformed']:,}"
        )

    print(
        f"Collections: present={collections['present']:,}, "
        f"missing={collections['missing']:,}, "
        f"malformed={collections['malformed']:,}"
    )

    print("\nMovies by decade")
    for decade, count in sorted(decades.items()):
        print(f"{decade}s: {count:,}")

    return seen_ids

def analyze_ratings():
    rows = 0
    invalid_rows = 0

    rating_counts = Counter()
    user_counts = Counter()
    ratings_by_movie = Counter()

    valid_ratings = {i / 2 for i in range(1, 11)}

    with (DATASET_PATH / "ratings.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows += 1

            try:
                user_id = int(row["userId"])
                movie_id = int(row["movieId"])
                rating = float(row["rating"])
                timestamp = int(row["timestamp"])
            except (ValueError, TypeError):
                invalid_rows += 1
                continue

            if (
                user_id <= 0
                or movie_id <= 0
                or rating not in valid_ratings
                or timestamp <= 0
            ):
                invalid_rows += 1
                continue

            rating_counts[rating] += 1
            user_counts[user_id] += 1
            ratings_by_movie[movie_id] += 1

    print("\nRatings")
    print(f"Rows: {rows:,}")
    print(f"Invalid rows: {invalid_rows:,}")
    print(f"Valid rows: {sum(rating_counts.values()):,}")
    print(f"Distinct users: {len(user_counts):,}")
    print(f"Distinct rated movies: {len(ratings_by_movie):,}")

    print("\nRating distribution")
    for rating, count in sorted(rating_counts.items()):
        print(f"{rating:.1f}: {count:,}")

    if user_counts:
        counts = list(user_counts.values())
        print(f"\nRatings per user")
        print(f"Mean: {sum(counts) / len(counts):.2f}")
        print(f"Median: {median(counts):g}")
        print(f"Maximum: {max(counts):,}")
        print(f"Users with >= 20 ratings: {sum(count >= 20 for count in counts):,}")

    return ratings_by_movie

def analyze_relationships(metadata_ids, credits_ids, keywords_ids, links, ratings_by_movie):
    print("\nMovie metadata relationships")
    for name, ids in (("Credits", credits_ids), ("Keywords", keywords_ids)):
        print(
            f"{name}: matched={len(metadata_ids & ids):,}, "
            f"metadata without {name.lower()}={len(metadata_ids - ids):,}, "
            f"{name.lower()} without metadata={len(ids - metadata_ids):,}"
        )

    print(f"Movies present in all three files: {len(metadata_ids & credits_ids & keywords_ids):,}")

    linked_tmdb_ids = {tmdb_id for tmdb_id in links.values() if tmdb_id is not None}

    print("\nTMDB mapping coverage")
    print(f"Linked TMDB IDs found in metadata: {len(linked_tmdb_ids & metadata_ids):,}")
    print(f"Linked TMDB IDs absent from metadata: {len(linked_tmdb_ids - metadata_ids):,}")
    print(f"Metadata IDs absent from links: {len(metadata_ids - linked_tmdb_ids):,}")

    rating_counts = Counter()
    movie_counts = Counter()

    for movie_id, count in ratings_by_movie.items():
        if movie_id not in links:
            category = "No MovieLens link"
        elif links[movie_id] is None:
            category = "Missing TMDB ID"
        elif links[movie_id] not in metadata_ids:
            category = "Missing movie metadata"
        else:
            category = "Matched"

        rating_counts[category] += count
        movie_counts[category] += 1

    print("\nRatings coverage")
    for category in ("Matched", "No MovieLens link", "Missing TMDB ID", "Missing movie metadata"):
        print(f"{category}: movies={movie_counts[category]:,}, ratings={rating_counts[category]:,}")

def main():
    credits_ids = analyze_credits()
    keywords_ids = analyze_keywords()
    links = analyze_links()
    metadata_ids = analyze_metadata()
    ratings_by_movie = analyze_ratings()
    analyze_relationships(metadata_ids, credits_ids, keywords_ids, links, ratings_by_movie)

if __name__ == "__main__":
    main()
