const database = db.getSiblingDB("tdt4225");

database.createUser({
    user: "tdt4225",
    pwd: process.env.MONGO_PASSWORD,
    roles: [{ role: "readWrite", db: "tdt4225" }]
});
