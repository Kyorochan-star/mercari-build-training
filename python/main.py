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


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"

db = pathlib.Path(__file__).parent.resolve() / "db" 
DB_PATH = db / "mercari.sqlite3"  # `db` ディレクトリ内の `mercari.sqlite3`

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
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

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


# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
def add_item(
    name: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

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

    # 入力チェック
    if not name or not category:
        raise HTTPException(status_code=400, detail="Both name and category are required")

    
    '''
    # アイテムの作成
    item = Item(name=name, category=category, image_name=image_filename)
    insert_item(item)  # アイテムを保存

    return AddItemResponse(**{"message": f"item received: name: {name}, category: {category}, image name: {item.image_name}"})
    '''

    cur = db.cursor()

    # `categories` テーブルから category_id を取得、存在しなければ新規作成
    cur.execute("SELECT id FROM categories WHERE name = ?", (category,))
    category_row = cur.fetchone()

    if category_row:
        category_id = category_row["id"]
    else:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (category,))
        category_id = cur.lastrowid

    # `category_id` を使って `items` テーブルにデータを保存
    cur.execute(
        "INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)",
        (name, category_id, image_filename),
    )
    db.commit()

    return AddItemResponse(message="Item added successfully", id=cur.lastrowid)




@app.get("/items",response_model=AddItemResponse)
async def get_items():
    ITEMS_FILE = "items.json"
    
    # JSONファイルを読み込む
    try:
        with open(ITEMS_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No items found")
    
    return AddItemResponse(message="Items fetched successfully", items=data["items"])


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

'''
def get_items_from_file():
    ITEMS_FILE = "items.json"
    
    # JSONファイルを読み込む
    try:
        with open(ITEMS_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No items found")
    
    return data["items"]
'''

@app.get("/items", response_model=AddItemResponse)
async def get_items(db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT items.id, items.name, categories.name as category, items.image_name 
        FROM items 
        JOIN categories ON items.category_id = categories.id
    """)
    items = [Item(**dict(row)) for row in cur.fetchall()]

    return AddItemResponse(message="Items fetched successfully", items=items)



# 商品詳細情報を取得するエンドポイント
'''
@app.get("/items/{item_id}")
async def get_item(item_id: int):
    items = get_items_from_file()  # 商品一覧を取得

    # item_idが範囲外の場合
    if item_id < 1 or item_id > len(items):
        raise HTTPException(status_code=404, detail="Item not found")

    # item_id番目の商品情報を返す
    item = items[item_id - 1]  # インデックスは0から始まるので1を引いて取得
    return item

class Item(BaseModel):
    name: str
    category: str
    image_name: str = None # 画像のファイル名（オプション）
'''

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


@app.get("/search", response_model=dict)
def search_items(keyword: str = Query(..., min_length=1), db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()

    # `JOIN` を使って category 名を取得
    cur.execute("""
        SELECT items.id, items.name, categories.name as category, items.image_name 
        FROM items 
        JOIN categories ON items.category_id = categories.id
        WHERE items.name LIKE ?
    """, (f"%{keyword}%",))
    
    # 返り値を `{"items": [...]}` の形にする
    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "image_name": row["image_name"]
        } 
        for row in cur.fetchall()
    ]
    return {"items": items}



def insert_item(item: Item, db: sqlite3.Connection):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO items (name, category, image_name) VALUES (?, ?, ?)",
        (item.name, item.category, item.image_name),
    )
    db.commit()
    '''
    # STEP 4-2: add an implementation to store an item

    ITEMS_FILE="items.json"

    # JSONファイルを読み込む
    try:
        with open(ITEMS_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        # ファイルがない場合は新しく作成
        data = {"items": []}
    
    # 新しいアイテムを追加
    new_item = {"name": item.name, "category": item.category, "image_name": item.image_name}
    data["items"].append(new_item)
    
    # ファイルに保存
    with open(ITEMS_FILE, "w") as f:
        json.dump(data, f, indent=4)
    '''


