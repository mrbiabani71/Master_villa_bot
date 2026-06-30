import { Router, type IRouter } from "express";
import Database from "better-sqlite3";
import path from "path";
import {
  ListVillasQueryParams,
  UpdateVillaStatusBody,
  UpdateVillaStatusParams,
  GetVillaParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

const DB_PATH = path.resolve(process.cwd(), "../../bot/bot.db");

function getDb() {
  return new Database(DB_PATH, { readonly: false });
}

router.get("/villas/stats", (req, res) => {
  const db = getDb();
  try {
    const total = (db.prepare("SELECT COUNT(*) as cnt FROM villas").get() as { cnt: number }).cnt;
    const active = (db.prepare("SELECT COUNT(*) as cnt FROM villas WHERE status = 'active'").get() as { cnt: number }).cnt;
    const inactive = total - active;

    const by_city = db
      .prepare("SELECT city, COUNT(*) as count FROM villas WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC")
      .all() as { city: string; count: number }[];

    const rows = db
      .prepare("SELECT price FROM villas WHERE price IS NOT NULL")
      .all() as { price: number }[];

    const tiers: Record<string, number> = {
      "اقتصادی": 0,
      "متوسط": 0,
      "نیمه لوکس": 0,
      "لوکس": 0,
    };
    for (const row of rows) {
      const p = row.price;
      if (p < 7_000_000_000) tiers["اقتصادی"]++;
      else if (p < 10_000_000_000) tiers["متوسط"]++;
      else if (p < 15_000_000_000) tiers["نیمه لوکس"]++;
      else tiers["لوکس"]++;
    }

    const by_price_tier = Object.entries(tiers).map(([tier, count]) => ({ tier, count }));

    res.json({ total, active, inactive, by_city, by_price_tier });
  } finally {
    db.close();
  }
});

router.get("/villas", (req, res) => {
  const parsed = ListVillasQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query params" });
    return;
  }
  const { status, city, area_type } = parsed.data;

  const db = getDb();
  try {
    let query = "SELECT * FROM villas WHERE 1=1";
    const params: unknown[] = [];

    if (status) { query += " AND status = ?"; params.push(status); }
    if (city) { query += " AND city = ?"; params.push(city); }
    if (area_type) { query += " AND area_type = ?"; params.push(area_type); }

    query += " ORDER BY created_at DESC";

    const rows = db.prepare(query).all(...params);
    res.json(rows);
  } finally {
    db.close();
  }
});

router.get("/villas/:id", (req, res) => {
  const parsed = GetVillaParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const db = getDb();
  try {
    const row = db.prepare("SELECT * FROM villas WHERE id = ?").get(parsed.data.id);
    if (!row) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }
    res.json(row);
  } finally {
    db.close();
  }
});

router.patch("/villas/:id", (req, res) => {
  const idParsed = UpdateVillaStatusParams.safeParse({ id: Number(req.params.id) });
  const bodyParsed = UpdateVillaStatusBody.safeParse(req.body);

  if (!idParsed.success || !bodyParsed.success) {
    res.status(400).json({ error: "Invalid request" });
    return;
  }

  const db = getDb();
  try {
    const existing = db.prepare("SELECT * FROM villas WHERE id = ?").get(idParsed.data.id);
    if (!existing) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }

    db.prepare("UPDATE villas SET status = ?, updated_at = datetime('now') WHERE id = ?")
      .run(bodyParsed.data.status, idParsed.data.id);

    const updated = db.prepare("SELECT * FROM villas WHERE id = ?").get(idParsed.data.id);
    res.json(updated);
  } finally {
    db.close();
  }
});

export default router;
