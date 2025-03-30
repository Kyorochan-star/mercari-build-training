import os
import logging
import pathlib
import json
import hashlib
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, File, UploadFile, Depends, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List
from typing import Optional
import sys
print("✅ print is working!", file=sys.stderr)


# 8-2 GitHub Actionの確認
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"

db = pathlib.Path(__file__).parent.resolve() / "db" 
DB_PATH = db / "mercari.sqlite3"  # `db` ディレクトリ内の `mercari.sqlite3`
print("📁 現在の作業ディレクトリ:", os.getcwd(), file=sys.stderr)
print("📄 DBファイル:", DB_PATH, file=sys.stderr)

# ディレクトリがない場合は作成
if not db.exists():
    db.mkdir(parents=True, exist_ok=True)

print(f"Database Path: {DB_PATH}")
print(f"Database Exists: {os.path.exists(DB_PATH)}")
print(f"DB Directory Exists: {os.path.exists(db)}")
print(f"DB Directory Path: {db}")

def get_db():
    if not db.exists():
        print(f"Database directory {db} not found. Creating it...")
        db.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print(f"Database file {DB_PATH} not found. Creating a new one...")
        open(DB_PATH, "w").close()  # 空のファイルを作成

    conn = sqlite3.connect(DB_PATH, check_same_thread=False) 
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # `categories` テーブル
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """)

    # `items` テーブル
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        image_name TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    """)

    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

@app.get("/debug-log")
def debug_log():
    print("🖨️ printが動きました！")
    logger.info("📦 logger.info が動きました！")
    return {"message": "Logged!"}

logger = logging.getLogger("uvicorn")
logger.level = logging.INFO
images = pathlib.Path(__file__).parent.resolve() / "images"
origins = [os.environ.get("FRONT_URL", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class HelloResponse(BaseModel):
    message: str


@app.get("/", response_model=HelloResponse)
def hello():
    return HelloResponse(**{"message": "Hello, world!"})


class AddItemResponse(BaseModel):
    message: str
    id: int
    items: Optional[List[dict]] = None  
    

# Pydantic モデルを定義（FastAPI に JSON を正しく認識させる）
class ItemRequest(BaseModel):
    name: str
    category: str


# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
async def add_item(
    name: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    print("🚀 POST /items にリクエストが届いた！", flush=True)
    

    # 入力チェック
    if not name or not category:
        raise HTTPException(status_code=400, detail="Both name and category are required")

    # 画像をSHA-256でハッシュ化して保存
    image_bytes = await image.read()  # 画像データを読み込む
    sha256_hash = hashlib.sha256(image_bytes).hexdigest()  # SHA-256ハッシュ化
    image_filename = f"{sha256_hash}.jpg"  # ハッシュ値をファイル名にして.jpg拡張子を追加


    # 画像を保存するディレクトリを確認、なければ作成
    image_dir = Path("images")
    if not image_dir.exists():
        image_dir.mkdir(parents=True)

    # 画像保存パス
    image_path = image_dir / image_filename

    # 画像ファイルを保存
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    

    cur = db.cursor()

    # `categories` テーブルから category_id を取得、存在しなければ新規作成
    cur.execute("SELECT id FROM categories WHERE name = ?", (category,))
    category_row = cur.fetchone()

    if category_row:
        category_id = category_row["id"]
    else:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (category,))
        db.commit()  #  `category` の `INSERT` を確定
        category_id = cur.lastrowid

    # `category_id` を使って `items` テーブルにデータを保存
    cur.execute(
        "INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)",
        (name, category_id, image_filename),
    )
    db.commit()

    item_id = cur.lastrowid  #  追加したアイテムの `id` を取得

    return AddItemResponse(message="Item added successfully", id=item_id)

# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(image)



class ItemsResponse(BaseModel):
    message: str
    items: list[dict]

# 商品詳細情報を取得するエンドポイント
@app.get("/items", response_model=ItemsResponse)
async def get_items(db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT items.id, items.name, categories.name as category, items.image_name 
        FROM items 
        JOIN categories ON items.category_id = categories.id
    """)
    items = [dict(row) for row in cur.fetchall()]

    return ItemsResponse(message="Items fetched successfully", items=items)


class Item(BaseModel):
    id: int
    name: str
    category: str
    image_name: str

@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT items.id, items.name, categories.name as category, items.image_name 
        FROM items 
        JOIN categories ON items.category_id = categories.id
        WHERE items.id = ?
    """, (item_id,))
    
    row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    return Item(id=row["id"], name=row["name"], category=row["category"], image_name=row["image_name"])


class SearchResponse(BaseModel):
    items: list[dict]


@app.get("/search", response_model=SearchResponse)
def search_items(keyword: str = Query(..., min_length=1), db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT items.id, items.name, categories.name as category, items.image_name 
        FROM items 
        JOIN categories ON items.category_id = categories.id
        WHERE items.name LIKE ?
    """, (f"%{keyword}%",))
    
    items = [dict(row) for row in cur.fetchall()]
    return SearchResponse(items=items)



