from flask import Flask, render_template_string, request, redirect
import json
import random
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import pytz
from collections import Counter
import re

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# JSONデータ読み込み
with open("twitter_reply_history_fixed.json", "r", encoding="utf-8") as f:
    user_histories = json.load(f)

for uid, data in user_histories.items():
    data["name"] = f"@{uid[:8]}…"

def get_greeting_instruction():
    jst = pytz.timezone('Asia/Tokyo')
    now_hour = datetime.now(jst).hour
    if 5 <= now_hour < 11:
        return "朝の時間帯です。挨拶として「おはようございます」など自然に使ってください。"
    elif 11 <= now_hour < 17:
        return "昼の時間帯です。「こんにちは」など自然な挨拶を使ってください。"
    elif 17 <= now_hour < 23:
        return "夕方〜夜の時間帯です。「こんばんは」など自然な挨拶を使ってください。"
    else:
        return "深夜帯です。挨拶は控えめでも構いませんが、丁寧な文体を心がけてください。"

def get_style_profile():
    all_texts = []
    for data in user_histories.values():
        all_texts.extend([c["text"] for c in data["comments"]])

    emoji_pattern = re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF]")
    emojis = Counter()
    phrases = Counter()

    for text in all_texts:
        emojis.update(emoji_pattern.findall(text))
        phrases.update(re.findall(r"[ぁ-んァ-ンーa-zA-Z一-龥]{2,6}", text))

    top_emojis = [e for e, _ in emojis.most_common(3)]
    top_phrases = [p for p, _ in phrases.most_common(10) if len(p) >= 3][:3]

    return f"""
あなたの文体の特徴：
- 優しく、ややカジュアル
- 語尾に「〜ですね」「〜ました」などが多い
- 絵文字は {', '.join(top_emojis)} をよく使います

よく使う表現：{', '.join(top_phrases)}
"""

def build_prompt(user_comment, past_replies):
    profile = get_style_profile()
    prompt = "あなたはTwitterアカウントの運営者です。\n"
    prompt += "以下の「過去の返信例」を参考に、次のコメントに対して自然な返信を3パターン考えてください。\n"
    prompt += "相手に親しみを込めて、あなたらしい語尾・表現・絵文字を活かした文体で書いてください。\n\n"
    prompt += profile + "\n"
    prompt += "## 過去の返信例:\n"
    for ex in past_replies:
        prompt += f"- {ex['text']}\n"
    prompt += f"\n## 新しいコメント:\n{user_comment}\n\n{get_greeting_instruction()}\n\n## 自然な返信候補:"
    return prompt

def build_generic_prompt(user_comment):
    profile = get_style_profile()
    prompt = f"""
あなたはTwitterアカウントの運営者です。
次のコメントに対して、自然で親しみのある返信を3パターン考えてください。
絵文字を適度に使い、口調はフレンドリーに。あなたの投稿らしい文体にしてください。

{get_greeting_instruction()}

{profile}

## 新しいコメント:
{user_comment}

## 自然な返信候補:
""".strip()
    return prompt

def get_past_replies(user, max_examples=3):
    if not user or user not in user_histories:
        return []
    examples = user_histories[user]["comments"]
    return random.sample(examples, min(len(examples), max_examples))

def save_log(username, user_comment, reply):
    with open("reply_log.csv", "a", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reply_text = reply.replace("\n", " ").replace(",", "。")
        f.write(f"{now},{username},{user_comment},{reply_text}\n")

@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    reply_options = []
    prompt = ""
    username = ""
    comment = ""
    if request.method == "POST" and "comment" in request.form:
        username = request.form["username"].strip()
        comment = request.form["comment"].strip()
        past_replies = get_past_replies(username)

        if past_replies:
            prompt = build_prompt(comment, past_replies)
        else:
            prompt = build_generic_prompt(comment)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        reply = response.choices[0].message.content
        reply_options = [opt.strip("- ") for opt in reply.strip().split("\n") if opt.strip()]
        save_log(username, comment, reply)

    sorted_users = sorted(user_histories.items(), key=lambda item: -len(item[1]['comments']))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Twitter返信アシスタント</title>
        <style>
            body { font-family: sans-serif; padding: 1em; max-width: 600px; margin: auto; }
            label { font-weight: bold; margin-top: 1em; display: block; }
            .form-group { margin-bottom: 1.2em; }
            select, textarea, button {
                width: 100%; padding: 0.8em; font-size: 1em;
                border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box;
            }
            button {
                background: #1da1f2; color: white; border: none; cursor: pointer; margin-top: 0.5em;
            }
            button:hover { background: #0d8ddb; }
            .card {
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 1em;
                margin-top: 1em;
            }
            .card p { margin: 0 0 0.5em 0; }
        </style>
        <script>
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text).then(() => alert("コピーしました！"));
            }
        </script>
    </head>
    <body>
        <h1>Twitter返信アシスタント</h1>
        <form method="post">
            <div class="form-group">
                <label>ユーザー名（@は除く）:</label>
                <select name="username">
                    <option value="">（履歴なしで生成）</option>
                    {% for uid, data in sorted_users %}
                        <option value="{{ uid }}" {% if username == uid %}selected{% endif %}>
                            {{ data['name'] }}（@{{ uid[:8] }}…）[{{ data['comments']|length }}件]
                        </option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>相手のコメント:</label>
                <textarea name="comment" rows="4" placeholder="コメント内容を入力してください" required>{{ comment }}</textarea>
            </div>
            <button type="submit">返信候補を生成</button>
        </form>

        {% if reply_options %}
            <h2>生成された返信候補</h2>
            {% for option in reply_options %}
                <div class="card">
                    <p>{{ option }}</p>
                    <button onclick="copyToClipboard('{{ option }}')">コピー</button>
                </div>
            {% endfor %}
        {% endif %}
    </body>
    </html>
    """, reply=reply, reply_options=reply_options, prompt=prompt, username=username, comment=comment, sorted_users=sorted_users)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)