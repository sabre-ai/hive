use std::path::PathBuf;
use std::sync::Mutex;

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use clap::Parser;
use log::info;
use serde::{Deserialize, Serialize};

use witchcraft::types::{
    SqlConditionInternal, SqlLogic, SqlOperator, SqlStatementInternal, SqlStatementType, SqlValue,
};
use witchcraft::{EmbeddingsCache, Embedder, DB};

// ── CLI ────────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(name = "hive-search", about = "HTTP search server for hive")]
struct Cli {
    /// Path to the witchcraft SQLite database
    #[arg(long, default_value = "~/.hive/search.db")]
    db_path: String,

    /// Path to the witchcraft model assets directory
    #[arg(long, env = "WARP_ASSETS")]
    assets: String,

    /// Port to listen on
    #[arg(long, default_value_t = 3033)]
    port: u16,
}

// ── Shared state ───────────────────────────────────────────────────────

struct AppState {
    db: Mutex<DB>,
    embedder: Embedder,
    cache: Mutex<EmbeddingsCache>,
    device: candle_core::Device,
}

// ── Request / Response types ───────────────────────────────────────────

#[derive(Deserialize)]
struct AddDocRequest {
    uuid: String,
    date: Option<String>,
    metadata: String,
    body: String,
    chunk_lengths: Option<Vec<usize>>,
}

#[derive(Deserialize)]
struct RemoveDocRequest {
    uuid: String,
}

#[derive(Deserialize)]
struct SearchRequest {
    query: String,
    threshold: Option<f32>,
    top_k: Option<usize>,
    use_fulltext: Option<bool>,
    filter: Option<FilterStatement>,
}

#[derive(Deserialize)]
struct IndexRequest {
    limit: Option<usize>,
}

#[derive(Serialize)]
struct SearchResult {
    score: f32,
    metadata: String,
    body: String,
    sub_idx: u32,
    date: String,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    doc_count: usize,
}

#[derive(Serialize)]
struct IndexResponse {
    embedded: usize,
    indexed: bool,
}

#[derive(Serialize)]
struct OkResponse {
    status: String,
}

// ── Filter types (JSON-friendly version of SqlStatementInternal) ──────

#[derive(Deserialize)]
struct FilterCondition {
    key: String,
    operator: String,
    value: Option<serde_json::Value>,
}

#[derive(Deserialize)]
struct FilterStatement {
    r#type: String,
    condition: Option<FilterCondition>,
    logic: Option<String>,
    statements: Option<Vec<FilterStatement>>,
}

fn parse_operator(op: &str) -> SqlOperator {
    match op {
        "Equals" | "=" => SqlOperator::Equals,
        "NotEquals" | "!=" => SqlOperator::NotEquals,
        "GreaterThan" | ">" => SqlOperator::GreaterThan,
        "LessThan" | "<" => SqlOperator::LessThan,
        "GreaterThanOrEquals" | ">=" => SqlOperator::GreaterThanOrEquals,
        "LessThanOrEquals" | "<=" => SqlOperator::LessThanOrEquals,
        "Like" => SqlOperator::Like,
        "NotLike" => SqlOperator::NotLike,
        "Exists" => SqlOperator::Exists,
        _ => SqlOperator::Equals,
    }
}

fn parse_filter(f: &FilterStatement) -> SqlStatementInternal {
    match f.r#type.as_str() {
        "Condition" => {
            let cond = f.condition.as_ref().map(|c| SqlConditionInternal {
                key: c.key.clone(),
                operator: parse_operator(&c.operator),
                value: c.value.as_ref().map(|v| match v {
                    serde_json::Value::String(s) => SqlValue::String(s.clone()),
                    serde_json::Value::Number(n) => {
                        SqlValue::Number(n.as_f64().unwrap_or_default())
                    }
                    _ => SqlValue::String(v.to_string()),
                }),
            });
            SqlStatementInternal {
                statement_type: SqlStatementType::Condition,
                condition: cond,
                logic: None,
                statements: None,
            }
        }
        "Group" => {
            let logic = f.logic.as_deref().map(|l| match l {
                "Or" => SqlLogic::Or,
                _ => SqlLogic::And,
            });
            let stmts = f
                .statements
                .as_ref()
                .map(|ss| ss.iter().map(parse_filter).collect());
            SqlStatementInternal {
                statement_type: SqlStatementType::Group,
                condition: None,
                logic,
                statements: stmts,
            }
        }
        _ => SqlStatementInternal {
            statement_type: SqlStatementType::Empty,
            condition: None,
            logic: None,
            statements: None,
        },
    }
}

// ── Handlers ───────────────────────────────────────────────────────────

async fn health(State(state): State<std::sync::Arc<AppState>>) -> Json<HealthResponse> {
    let count = {
        let db = state.db.lock().unwrap();
        db.query("SELECT COUNT(*) FROM document")
            .and_then(|mut q| q.query_row((), |row| row.get::<_, usize>(0)))
            .unwrap_or(0)
    };
    Json(HealthResponse {
        status: "ok".into(),
        doc_count: count,
    })
}

async fn add_doc(
    State(state): State<std::sync::Arc<AppState>>,
    Json(req): Json<AddDocRequest>,
) -> Result<Json<OkResponse>, (StatusCode, String)> {
    let uuid = uuid::Uuid::parse_str(&req.uuid).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid uuid: {e}"),
        )
    })?;
    let date = req
        .date
        .as_deref()
        .and_then(iso8601_timestamp::Timestamp::parse);
    let mut db = state.db.lock().unwrap();
    db.add_doc(&uuid, date, &req.metadata, &req.body, req.chunk_lengths)
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("add_doc failed: {e}"),
            )
        })?;
    Ok(Json(OkResponse {
        status: "ok".into(),
    }))
}

async fn remove_doc(
    State(state): State<std::sync::Arc<AppState>>,
    Json(req): Json<RemoveDocRequest>,
) -> Result<Json<OkResponse>, (StatusCode, String)> {
    let uuid = uuid::Uuid::parse_str(&req.uuid).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid uuid: {e}"),
        )
    })?;
    let mut db = state.db.lock().unwrap();
    db.remove_doc(&uuid).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("remove_doc failed: {e}"),
        )
    })?;
    Ok(Json(OkResponse {
        status: "ok".into(),
    }))
}

async fn search(
    State(state): State<std::sync::Arc<AppState>>,
    Json(req): Json<SearchRequest>,
) -> Result<Json<Vec<SearchResult>>, (StatusCode, String)> {
    let threshold = req.threshold.unwrap_or(0.0);
    let top_k = req.top_k.unwrap_or(20);
    let use_fulltext = req.use_fulltext.unwrap_or(true);

    let filter = req.filter.as_ref().map(parse_filter);

    let db = state.db.lock().unwrap();
    let mut cache = state.cache.lock().unwrap();

    let results = witchcraft::search(
        &db,
        &state.embedder,
        &mut cache,
        &req.query,
        threshold,
        top_k,
        use_fulltext,
        filter.as_ref(),
    )
    .map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("search failed: {e}"),
        )
    })?;

    let out: Vec<SearchResult> = results
        .into_iter()
        .map(|(score, metadata, bodies, sub_idx, date)| {
            let body = bodies
                .get(sub_idx as usize)
                .cloned()
                .unwrap_or_default();
            SearchResult {
                score,
                metadata,
                body,
                sub_idx,
                date,
            }
        })
        .collect();

    Ok(Json(out))
}

async fn index(
    State(state): State<std::sync::Arc<AppState>>,
    Json(req): Json<IndexRequest>,
) -> Result<Json<IndexResponse>, (StatusCode, String)> {
    let db = state.db.lock().unwrap();

    let embedded = witchcraft::embed_chunks(&db, &state.embedder, req.limit).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("embed_chunks failed: {e}"),
        )
    })?;

    witchcraft::index_chunks(&db, &state.device).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("index_chunks failed: {e}"),
        )
    })?;

    Ok(Json(IndexResponse {
        embedded,
        indexed: true,
    }))
}

// ── Main ───────────────────────────────────────────────────────────────

fn expand_tilde(path: &str) -> PathBuf {
    if let Some(rest) = path.strip_prefix("~/") {
        if let Some(home) = dirs_home(rest) {
            return home;
        }
    }
    PathBuf::from(path)
}

fn dirs_home(rest: &str) -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| PathBuf::from(h).join(rest))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let cli = Cli::parse();
    let db_path = expand_tilde(&cli.db_path);
    let assets_path = expand_tilde(&cli.assets);

    // Ensure parent directory exists
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    info!("loading model from {}...", assets_path.display());
    let device = witchcraft::make_device();
    let embedder = Embedder::new(&device, &assets_path)?;
    info!("model loaded.");

    let db = DB::new(db_path)?;

    let state = std::sync::Arc::new(AppState {
        db: Mutex::new(db),
        embedder,
        cache: Mutex::new(EmbeddingsCache::new(64)),
        device,
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/add", post(add_doc))
        .route("/remove", post(remove_doc))
        .route("/search", post(search))
        .route("/index", post(index))
        .with_state(state);

    let addr = format!("0.0.0.0:{}", cli.port);
    info!("hive-search listening on {addr}");
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
