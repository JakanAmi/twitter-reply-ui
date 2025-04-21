from flask import Flask, render_template_string, request
import json
import random
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# JSONデータ読み込み
with open("twitter_reply_history_fixed.json", "r", encoding="utf-8") as f:
    user_histories = json.load(f)

# プロンプト生成関数
def build_prompt(user_comment, past_replies):
    prompt = "あなたはTwitterアカウントの運営者です。\n"
    prompt += "以下の「過去の返信例」を参考に、次のコメントに対して自然な返信を3パターン考えてください。\n"
    prompt += "相手に親しみを込めて、あなたらしい語尾・表現・絵文字を活かした文体で書いてください。\n\n"
    prompt += "## 過去の返信例:\n"
    for ex in past_replies:
        prompt += f"- {ex['text']}\n"
    prompt += f"\n## 新しいコメント:\n{user_comment}\n\n## 自然な返信候補:"
    return prompt

# ランダムに過去の返信を取得
def get_past_replies(user, max_examples=3):
    if user not in user_histories:
        return []
    examples = user_histories[user]["comments"]
    return random.sample(examples, min(len(examples), max_examples))

# ログ保存関数
def save_log(username, user_comment, reply):
    with open("reply_log.csv", "a", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reply_text = reply.replace("\n", " ").replace(",", "。")
        f.write(f"{now},{username},{user_comment},{reply_text}\n")

# UIルート
@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    prompt = ""
    username = ""
    comment = ""
    if request.method == "POST":
        username = request.form["username"].strip()
        comment = request.form["comment"].strip()
        past_replies = get_past_replies(username)
        if past_replies:
            prompt = build_prompt(comment, past_replies)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            reply = response.choices[0].message.content
            save_log(username, comment, reply)
        else:
            reply = "⚠️ ユーザーの過去の返信が見つかりませんでした。"

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Twitter返信アシスタント</title>
        <style>
            body {
                font-family: sans-serif;
                padding: 1em;
                max-width: 600px;
                margin: auto;
            }
            input, textarea, select, button {
                width: 100%;
                padding: 0.7em;
                margin-top: 0.5em;
                margin-bottom: 1em;
                font-size: 1em;
            }
            button {
                background: #1da1f2;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }
            button:hover {
                background: #0d8ddb;
            }
            .reply-box {
                background: #f4f4f4;
                padding: 1em;
                border-left: 5px solid #1da1f2;
                white-space: pre-wrap;
                margin-top: 1em;
            }
        </style>
    </head>
    <body>
        <h1>Twitter返信アシスタント</h1>
        <form method="post">
            <label>ユーザー名（@は除く）:</label>
            <input type="text" name="username" value="{{ username }}" required>

            <label>相手のコメント:</label>
            <textarea name="comment" rows="4" required>{{ comment }}</textarea>

            <button type="submit">返信候補を生成</button>
        </form>

        {% if reply %}<div class="reply-box">{{ reply }}</div>{% endif %}
    </body>
    </html>
    """, reply=reply, prompt=prompt, username=username, comment=comment)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
