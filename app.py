from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
from datetime import datetime
import pytz
from openai import OpenAI
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super-secret")

# データ読み込み
with open("twitter_reply_history_fixed.json", "r", encoding="utf-8") as f:
    twitter_data = json.load(f)

with open("yamap_reply_history.json", "r", encoding="utf-8") as f:
    yamap_data = json.load(f)

data_sources = {
    "twitter": twitter_data,
    "yamap": yamap_data
}

def detect_emotion(comment):
    if any(word in comment for word in ["ありがとう", "嬉しい", "最高"]):
        return "joy"
    elif any(word in comment for word in ["つらい", "痛い", "残念"]):
        return "sadness"
    elif any(word in comment for word in ["なんで", "ひどい", "怒"]):
        return "anger"
    elif any(word in comment for word in ["どうしよう", "迷う", "不安"]):
        return "confused"
    return None

def detect_tone(comment):
    casual_keywords = ["ね", "よ", "〜", "笑", "だよ", "やば"]
    polite_keywords = ["です", "ます", "でしょう", "ですね"]
    casual = sum(1 for word in casual_keywords if word in comment)
    polite = sum(1 for word in polite_keywords if word in comment)

    if casual > polite:
        return "カジュアル"
    elif polite > casual:
        return "丁寧"
    else:
        return "普通"

def get_greeting():
    jst = pytz.timezone('Asia/Tokyo')
    current_hour = datetime.now(jst).hour
    if current_hour < 10:
        return "おはようございます"
    elif current_hour < 17:
        return "こんにちは"
    else:
        return "こんばんは"

def generate_reply(user_id, comment, platform):
    user_data = data_sources[platform].get(user_id)
    greeting = get_greeting()
    emotion = detect_emotion(comment)
    tone = detect_tone(comment)
    
    # プロンプト生成
    prompt = f"""
あなたは{platform.upper()}アカウントの運営者です。
以下の「過去の返信例」を参考に、次のコメントに対して自然な返信を3パターン考えてください。
なるべく過去の文体（語尾、口調、絵文字）を活かしてください。
{f"感情トーン：{emotion} に合わせて返信してください。" if emotion else ""}
{f"文体は「{tone}」な雰囲気を意識してください。" if tone else ""}

## 過去の返信例:
"""
    if user_data:
        for c in user_data["comments"]:
            prompt += f"- {c['text']}\n- {c['reply']}\n"
    else:
        prompt += "（過去の返信が見つかりませんでした）\n"

    prompt += f"""

## 新しいコメント:
{comment}

## 返信候補:
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        comment = request.form.get('comment')
        platform = request.form.get('platform', 'twitter')
        from hashlib import sha256
        if 'reply_cache' not in session:
            session['reply_cache'] = {}

        key = sha256(f"{user_id}-{comment}-{platform}".encode('utf-8')).hexdigest()
        reply_cache = session['reply_cache']

        if key in reply_cache:
            generated_reply = reply_cache[key]
        else:
            generated_reply = generate_reply(user_id, comment, platform)
            reply_cache[key] = generated_reply

        session['generated'] = generated_reply
        session['reply_cache'] = reply_cache
        session['selected_platform'] = platform
        session['user_id'] = user_id
        return redirect(url_for('index'))

    generated = session.pop('generated', None)
    selected_platform = session.pop('selected_platform', 'twitter')
    user_id = session.pop('user_id', '')
    user_ids = list(data_sources[selected_platform].keys())

    return render_template('index.html',
                           user_ids=user_ids,
                           generated=generated,
                           selected_platform=selected_platform,
                           selected_user_id=user_id)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8080)
