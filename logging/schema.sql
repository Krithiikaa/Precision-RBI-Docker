CREATE DATABASE IF NOT EXISTS rbi;

CREATE TABLE IF NOT EXISTS rbi.audit
(
    ts          DateTime64(3) DEFAULT now64(),
    user_id     String,
    session_id  String,
    event_type  String,
    url         String,
    meta        String
)
ENGINE = MergeTree
ORDER BY (user_id, ts);
