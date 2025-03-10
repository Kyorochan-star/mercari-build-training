import os
import logging
import pathlib
import json
import hashlib
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, File, UploadFile, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"


def get_db():
    if not db.exists():
        yield

    conn = sqlite3.connect(db)
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
    items: List[dict]  # itemsのリストを追加


# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
async def add_item(
    name: str = Form(...),
    category: str =Form(...),
    image: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):

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

    # アイテムの作成
    item = Item(name=name, category=category, image_name=image_filename)
    insert_item(item)  # アイテムを保存

    return AddItemResponse(**{"message": f"item received: name: {name}, category: {category}, image name: {item.image_name}"})



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

def get_items_from_file():
    ITEMS_FILE = "items.json"
    
    # JSONファイルを読み込む
    try:
        with open(ITEMS_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No items found")
    
    return data["items"]

# 商品詳細情報を取得するエンドポイント
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


def insert_item(item: Item):
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

