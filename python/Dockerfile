# ベースイメージとして Alpine を使用
FROM alpine

# 必要なパッケージをインストール
RUN apk update && apk add --no-cache python3 py3-pip sqlite

# 作業ディレクトリを設定
WORKDIR /app

# Python の仮想環境を作成し、そこに `pip` でライブラリをインストール
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 依存ライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコンテナにコピー
COPY . .

# ポート 9000 を開放
EXPOSE 9000

# アプリケーションを起動（Uvicorn を使用）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
