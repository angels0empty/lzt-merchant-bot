import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "payments.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                result_id TEXT,
                amount INTEGER,
                inline_message_id TEXT,
                invoice_url TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_result_id ON payments(result_id)")
        await db.commit()


async def add_payment(payment_id: str, result_id: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO payments (payment_id, result_id, amount) VALUES (?, ?, ?)",
            (payment_id, result_id, amount)
        )
        await db.commit()


async def get_payment_by_result_id(result_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE result_id = ?", (result_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def update_payment(payment_id: str, inline_message_id: str = None, invoice_url: str = None, status: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        updates = []
        params = []
        if inline_message_id:
            updates.append("inline_message_id = ?")
            params.append(inline_message_id)
        if invoice_url:
            updates.append("invoice_url = ?")
            params.append(invoice_url)
        if status:
            updates.append("status = ?")
            params.append(status)

        if updates:
            params.append(payment_id)
            await db.execute(
                f"UPDATE payments SET {', '.join(updates)} WHERE payment_id = ?",
                params
            )
            await db.commit()


async def get_payment(payment_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None
