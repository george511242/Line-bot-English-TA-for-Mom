from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)
import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# 初始化 Flask 應用
app = Flask(__name__)

# LINE Channel 金鑰與 Secret
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 設定 Gemini API 金鑰
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def generate_color_from_text(text: str) -> str:
    """
    使用 Gemini 生成英文教學回覆
    """
    prompt = f"""
    你是一個「來自台灣英文線上家教」。你的任務是：

    1. 以中文說明，從使用者的英文問題給予教學。
    2. 單字則給予kk音標、中文翻譯、同義字、和例句。
    3. 文法則詳細解釋。
    4. 若學生問英文作文如何寫，給予教學

    請嚴格按照下面格式輸出（純 JSON，不要多餘文字）：
    ```
    {{
    "reply": "這裡放你的回覆……"
    }}
    ```
    使用者問題：{text}
    """
    try:
        model = genai.GenerativeModel('models/gemini-3-flash')
        response = model.generate_content(prompt)

        print("==== Gemini API Raw Response ====")
        print(response)
        print("=================================")

        # 取出真正的回覆文字
        content = response.candidates[0].content.parts[0].text.strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        result = json.loads(content)

        return result["reply"]

    except Exception as e:
        print("Gemini API 錯誤：", e)
        return "抱歉，我暫時無法理解你的問題，但我會一直在你身邊。"


@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭
    signature = request.headers['X-Line-Signature']

    # 取得請求體
    body = request.get_data(as_text=True)
    print("Request body: " + body)

    # 驗證訊息是否來自 LINE
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

def format_reply(text: str) -> str:
    # 移除多餘的 Markdown 星號符號
    text = text.replace("**", "")

    # 把 Gemini 回覆以換行拆成段落
    paragraphs = text.split('\n')

    formatted_lines = []
    for line in paragraphs:
        line = line.strip()
        if not line:
            continue  # 跳過空行

        # 對常見的條列符號做替換，讓排版更清楚
        if line.startswith("*"):
            # 用中文圓點替代
            line = "・" + line.lstrip("* ").strip()
            # 增加縮排
            line = "    " + line
        elif line.startswith("-"):
            line = "・" + line.lstrip("- ").strip()
            line = "    " + line
        # 你可以針對其他格式再增加條件

        formatted_lines.append(line)

    # 合併成最後文字，並保留兩行換行避免段落過擠
    formatted_text = "\n\n".join(formatted_lines)

    # 避免過多連續空行
    formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)

    return formatted_text.strip()


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply_text = generate_color_from_text(user_text)

    if not reply_text:
        reply_text = "抱歉，我暫時無法理解你的問題，但我會一直在你身邊。"

    # 用格式化函式整理回覆內容
    reply_text = format_reply(reply_text)

    print("Reply to user:", repr(reply_text))

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )



if __name__ == "__main__":
    app.run(debug=True)
