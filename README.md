# LZT Payment Inline Bot

Simple telegram bot for generating payment links via inline mode for lzt.market

## Preparation

1. Get your lzt.market API token at https://lzt.market/account/api
2. Create your merchant at https://lzt.market/merchants and copy the merchant key

## Usage

1. Copy `.env.example` to `.env` and fill in your values
2. Install deps: `pip install -r requirements.txt`
3. Run: `python bot.py`

## Inline mode

type `@your_bot_name 1000` in any chat to create invoice for 1000 RUB

## Getting IMAGE file_id

Send any photo to your bot and handle it with temporary handler to get file_id:

```python
@dp.message_handler(content_types=['photo'])
async def get_photo_id(msg: types.Message):
    await msg.reply(msg.photo[-1].file_id)
```

## Webhook

Bot runs FastAPI server on port 80. Set your `CALLBACK_URL` to `https://your-domain.com/webhook/payment`

## Notes

- Bot uses inline_feedback mode - enable it via @BotFather (Inline Feedback -> 100%)
- Domain is not required — you can use IP address directly: `http://123.45.67.89/webhook/payment`
