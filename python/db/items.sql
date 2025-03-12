BEGIN TRANSACTION;

-- `old_items` を削除（何度も実行可能にするため）
DROP TABLE IF EXISTS old_items;

-- `items` テーブルが存在する場合のみ `old_items` にリネーム
ALTER TABLE items RENAME TO old_items;

-- `items` テーブルを作成（`category_id` を使う形に変更）
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    image_name TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- `old_items` から `items` にデータを移行
INSERT INTO items (name, category_id, image_name)
SELECT old_items.name, categories.id, old_items.image_name
FROM old_items
JOIN categories ON old_items.category = categories.name;

-- `categories` に存在しないカテゴリを追加
INSERT OR IGNORE INTO categories (name) 
SELECT DISTINCT old_items.category FROM old_items;

-- デフォルトカテゴリ `'Unknown'` を追加（存在しない場合のみ）
INSERT OR IGNORE INTO categories (name) VALUES ('Unknown');

-- `category_id` が `NULL` の場合、デフォルトの `'Unknown'` カテゴリをセット
UPDATE items 
SET category_id = (SELECT id FROM categories WHERE name = 'Unknown') 
WHERE category_id IS NULL;

-- `old_items` は不要になったため削除
DROP TABLE old_items;

COMMIT;





