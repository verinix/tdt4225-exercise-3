from statistics import median
from tabulate import tabulate
from DbConnector import DbConnector
from collections import defaultdict
from itertools import combinations, product

def task_1(db):
    pipeline = [
        {"$unwind": "$crew"},
        {"$match": {"crew.job": "Director"}},
        {"$group": {
            "_id": {"director": "$crew.id", "movie": "$_id"},
            "name": {"$first": "$crew.name"},
            "revenue": {"$first": "$revenue"},
            "vote_average": {"$first": "$vote_average"}
        }},
        {"$group": {
            "_id": "$_id.director",
            "name": {"$first": "$name"},
            "movie_count": {"$sum": 1},
            "mean_vote_average": {"$avg": "$vote_average"},
            "revenues": {"$push": "$revenue"}
        }},
        {"$match": {"movie_count": {"$gte": 5}}}
    ]

    rows = []

    for director in db.movies.aggregate(pipeline):
        revenues = [value for value in director["revenues"] if value is not None]

        if not revenues:
            continue

        rows.append((
            director["name"],
            director["movie_count"],
            median(revenues),
            director["mean_vote_average"],
        ))

    rows.sort(key=lambda row: row[2], reverse=True)

    print("\nTask 1")
    print(tabulate(
        rows[:10],
        headers=["Director", "Movies", "Median revenue ($)", "Mean vote average"],
        floatfmt=".2f"
    ))

def task_2(db):
    movies = db.movies.find(
        {"cast.1": {"$exists": True}},
        {"cast.id": 1, "cast.name": 1, "vote_average": 1}
    )

    actor_names = {}
    pair_stats = defaultdict(lambda: [0, 0.0, 0])

    for movie in movies:
        actors = {person["id"]: person["name"] for person in movie["cast"]}
        actor_names.update(actors)

        for pair in combinations(sorted(actors), 2):
            stats = pair_stats[pair]
            stats[0] += 1

            if movie["vote_average"] is not None:
                stats[1] += movie["vote_average"]
                stats[2] += 1

    rows = []

    for (actor_a, actor_b), (movie_count, vote_total, vote_count) in pair_stats.items():
        if movie_count < 3:
            continue

        mean_vote_average = vote_total / vote_count if vote_count else None

        rows.append((
            actor_names[actor_a],
            actor_names[actor_b],
            movie_count,
            mean_vote_average,
        ))

    rows.sort(key=lambda row: row[2], reverse=True)

    print("\nTask 2")
    print(f"Qualifying pairs: {len(rows):,}")
    print(tabulate(
        rows[:20],
        headers=["Actor 1", "Actor 2", "Movies", "Mean vote average"],
        floatfmt=".2f"
    ))

    if len(rows) > 20:
        print("Showing first 20 pairs.")

def task_3(db):
    pipeline = [
        {"$unwind": "$cast"},
        {"$group": {
            "_id": {"actor": "$cast.id", "movie": "$_id"},
            "name": {"$first": "$cast.name"},
            "genres": {"$first": "$genres"}
        }},
        {"$group": {
            "_id": "$_id.actor",
            "name": {"$first": "$name"},
            "movie_count": {"$sum": 1},
            "genre_lists": {"$push": "$genres"}
        }},
        {"$match": {"movie_count": {"$gte": 10}}}
    ]

    rows = []

    for actor in db.movies.aggregate(pipeline):
        genres = {
            genre["id"]: genre["name"]
            for genre_list in actor["genre_lists"]
            for genre in genre_list
        }

        rows.append((
            actor["name"],
            actor["movie_count"],
            len(genres),
            ", ".join(list(genres.values())[:5])
        ))

    rows.sort(key=lambda row: row[2], reverse=True)

    print("\nTask 3")
    print(tabulate(
        rows[:10],
        headers=["Actor", "Movies", "Distinct genres", "Example genres"]
    ))

def task_4(db):
    pipeline = [
        {"$match": {"belongs_to_collection.name": {"$ne": None}}},
        {"$group": {
            "_id": "$belongs_to_collection.id",
            "name": {"$first": "$belongs_to_collection.name"},
            "movie_count": {"$sum": 1},
            "total_revenue": {"$sum": "$revenue"},
            "vote_averages": {"$push": "$vote_average"},
            "earliest_release": {"$min": "$release_date"},
            "latest_release": {"$max": "$release_date"}
        }},
        {"$match": {"movie_count": {"$gte": 3}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 10}
    ]

    rows = []

    for collection in db.movies.aggregate(pipeline):
        vote_averages = [
            value for value in collection["vote_averages"]
            if value is not None
        ]
        median_vote = median(vote_averages) if vote_averages else None

        earliest = collection["earliest_release"]
        latest = collection["latest_release"]

        rows.append((
            collection["name"],
            collection["movie_count"],
            collection["total_revenue"],
            median_vote,
            earliest.date() if earliest else None,
            latest.date() if latest else None
        ))

    print("\nTask 4")
    print(tabulate(
        rows,
        headers=[
            "Collection",
            "Movies",
            "Total revenue ($)",
            "Median vote average",
            "Earliest release",
            "Latest release"
        ],
        floatfmt=".2f"
    ))

def task_5(db):
    pipeline = [
        {"$match": {
            "release_date": {"$ne": None},
            "genres.0": {"$exists": True}
        }},
        {"$project": {
            "decade": {
                "$multiply": [
                    {"$floor": {"$divide": [{"$year": "$release_date"}, 10]}},
                    10
                ]
            },
            "genre": {"$arrayElemAt": ["$genres.name", 0]},
            "runtime": 1
        }},
        {"$group": {
            "_id": {"decade": "$decade", "genre": "$genre"},
            "movie_count": {"$sum": 1},
            "runtimes": {"$push": "$runtime"}
        }}
    ]

    rows = []

    for group in db.movies.aggregate(pipeline):
        runtimes = [value for value in group["runtimes"] if value is not None]
        rows.append((
            int(group["_id"]["decade"]),
            group["_id"]["genre"],
            group["movie_count"],
            median(runtimes) if runtimes else None
        ))

    rows.sort(key=lambda row: (row[0], -(row[3] or 0)))

    print("\nTask 5")
    print(f"Groups found: {len(rows):,}")
    print(tabulate(
        rows[-20:],
        headers=["Decade", "Primary genre", "Movies", "Median runtime (min)"],
        floatfmt=".1f"
    ))

    if len(rows) > 20:
        print("Showing last 20 groups (most recent decades).")

def task_6(db):
    pipeline = [
        {"$match": {
            "release_date": {"$ne": None},
            "cast.0": {"$exists": True}
        }},
        {"$project": {
            "decade": {
                "$multiply": [
                    {"$floor": {"$divide": [{"$year": "$release_date"}, 10]}},
                    10
                ]
            },
            "cast.gender": 1
        }}
    ]

    decade_stats = defaultdict(lambda: [0.0, 0])

    for movie in db.movies.aggregate(pipeline):
        top_cast = movie["cast"][:5]
        known = [actor for actor in top_cast if actor["gender"] in (1, 2)]

        if not known:
            continue

        female_count = sum(actor["gender"] == 1 for actor in known)
        female_proportion = female_count / len(known)

        stats = decade_stats[int(movie["decade"])]
        stats[0] += female_proportion
        stats[1] += 1

    rows = [
        (decade, total / count, count)
        for decade, (total, count) in decade_stats.items()
    ]
    rows.sort(key=lambda row: row[1], reverse=True)

    print("\nTask 6")
    print(tabulate(
        rows,
        headers=["Decade", "Mean female proportion", "Movies"],
        floatfmt=".3f"
    ))

def task_7(db):
    pipeline = [
        {"$match": {
            "$text": {"$search": "noir"},
            "vote_count": {"$gte": 50}
        }},
        {"$sort": {"vote_average": -1}},
        {"$limit": 20},
        {"$project": {
            "_id": 0,
            "title": 1,
            "year": {"$year": "$release_date"},
            "vote_average": 1,
            "vote_count": 1
        }}
    ]

    rows = []

    for movie in db.movies.aggregate(pipeline):
        rows.append((
            movie["title"],
            movie["year"],
            movie["vote_average"],
            movie["vote_count"]
        ))

    print("\nTask 7")
    print(tabulate(
        rows,
        headers=["Title", "Year", "Vote average", "Vote count"],
        floatfmt=".2f"
    ))

def task_8(db):
    movies = db.movies.find(
        {
            "vote_count": {"$gte": 100},
            "cast.0": {"$exists": True},
            "crew.job": "Director"
        },
        {
            "cast.id": 1,
            "cast.name": 1,
            "crew.id": 1,
            "crew.name": 1,
            "crew.job": 1,
            "vote_average": 1,
            "revenue": 1
        }
    )

    director_names = {}
    actor_names = {}
    pair_stats = defaultdict(lambda: [0, 0.0, 0, 0, 0])

    for movie in movies:
        directors = {
            person["id"]: person["name"]
            for person in movie["crew"]
            if person["job"] == "Director"
        }
        actors = {
            person["id"]: person["name"]
            for person in movie["cast"]
        }

        director_names.update(directors)
        actor_names.update(actors)

        for pair in product(directors, actors):
            stats = pair_stats[pair]
            stats[0] += 1

            if movie["vote_average"] is not None:
                stats[1] += movie["vote_average"]
                stats[2] += 1

            if movie["revenue"] is not None:
                stats[3] += movie["revenue"]
                stats[4] += 1

    rows = []

    for (director_id, actor_id), stats in pair_stats.items():
        movie_count, vote_total, vote_count, revenue_total, revenue_count = stats

        if movie_count < 3 or vote_count == 0:
            continue

        mean_vote_average = vote_total / vote_count
        mean_revenue = revenue_total / revenue_count if revenue_count else None

        rows.append((
            director_names[director_id],
            actor_names[actor_id],
            movie_count,
            mean_vote_average,
            mean_revenue
        ))

    rows.sort(key=lambda row: row[3], reverse=True)

    print("\nTask 8")
    print(f"Qualifying pairs: {len(rows):,}")
    print(tabulate(
        rows[:20],
        headers=["Director", "Actor", "Movies", "Mean vote average", "Mean revenue ($)"],
        floatfmt=".2f"
    ))

    if len(rows) > 20:
        print("Showing first 20 pairs.")

def task_9(db):
    pipeline = [
        {"$match": {
            "original_language": {"$nin": ["en", None]},
            "production_countries.iso_3166_1": "US"
        }},
        {"$group": {
            "_id": "$original_language",
            "movie_count": {"$sum": 1},
            "example_title": {"$first": "$title"}
        }},
        {"$sort": {"movie_count": -1}},
        {"$limit": 10}
    ]

    rows = []

    for language in db.movies.aggregate(pipeline):
        rows.append((
            language["_id"],
            language["movie_count"],
            language["example_title"],
        ))

    print("\nTask 9")
    print(tabulate(
        rows,
        headers=["Original language", "Movies", "Example title"]
    ))

def task_10(db):
    movie_genres = {
        movie["_id"]: {genre["id"] for genre in movie["genres"]}
        for movie in db.movies.find({}, {"genres.id": 1})
    }

    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "rating_count": {"$sum": 1},
            "stddev": {"$stdDevPop": "$rating"},
            "movie_ids": {"$addToSet": "$tmdb_id"}
        }}
    ]

    rows = []

    for user in db.ratings.aggregate(pipeline):
        genres = set()

        for movie_id in user["movie_ids"]:
            genres.update(movie_genres.get(movie_id, set()))

        rows.append((
            user["_id"],
            user["rating_count"],
            user["stddev"] ** 2,
            len(genres),
        ))

    most_diverse = sorted(
        rows,
        key=lambda row: row[3],
        reverse=True
    )[:10]

    highest_variance = sorted(
        (row for row in rows if row[1] >= 20),
        key=lambda row: row[2],
        reverse=True
    )[:10]

    headers = ["User", "Ratings", "Population variance", "Distinct genres"]

    print("\nTask 10: Most diverse")
    print(tabulate(most_diverse, headers=headers, floatfmt=".3f"))

    print("\nTask 10: Highest rating variance")
    print(tabulate(highest_variance, headers=headers, floatfmt=".3f"))

def main():
    database = DbConnector()

    try:
        task_1(database.db)
        task_2(database.db)
        task_3(database.db)
        task_4(database.db)
        task_5(database.db)
        task_6(database.db)
        task_7(database.db)
        task_8(database.db)
        task_9(database.db)
        task_10(database.db)
    finally:
        database.close_connection()

if __name__ == "__main__":
    main()
