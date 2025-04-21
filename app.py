from flask import Flask, render_template_string, request
import json
import random
import os
from dotenv import load_dotenv
from openai import OpenAI

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
    prompt += "なるべく過去の文体（語尾、口調、絵文字）を活かしてください。\n\n"
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

# UIルート
@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    prompt = ""
    if request.method == "POST":
        username = request.form["username"].strip()
        comment = request.form["comment"].strip()
        past_replies = get_past_replies(username)
        if past_replies:
            prompt = build_prompt(comment, past_replies)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            reply = response.choices[0].message.content
        else:
            reply = "⚠️ ユーザーの過去の返信が見つかりませんでした。"

    return render_template_string("""
    <html>
    <head>
        <title>Twitter返信アシスタント</title>
    </head>
    <body>
        <h1>Twitter返信アシスタント</h1>
        <form method="post">
            <label>ユーザー名（@は除く）:</label><br>
            <input type="text" name="username" required><br><br>
            <label>相手のコメント:</label><br>
            <textarea name="comment" rows="4" cols="50" required></textarea><br><br>
            <button type="submit">返信候補を生成</button>
        </form>
        <hr>
        {% if prompt %}<h3>プロンプト</h3><pre>{{ prompt }}</pre>{% endif %}
        {% if reply %}<h3>生成された返信候補</h3><pre>{{ reply }}</pre>{% endif %}
    </body>
    </html>
    """, reply=reply, prompt=prompt)

if __name__ == "__main__":
    app.run(debug=True)