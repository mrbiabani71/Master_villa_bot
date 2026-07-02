import { Router, type IRouter } from "express";
import Database from "better-sqlite3";
import path from "path";
import {
  ListVillasQueryParams,
  CreateVillaBody,
  UpdateVillaParams,
  UpdateVillaBody,
  UpdateVillaStatusBody,
  UpdateVillaStatusParams,
  GetVillaParams,
  ArchiveVillaParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

const DB_PATH = path.resolve(process.cwd(), "../../bot/bot.db");

function getDb() {
  return new Database(DB_PATH, { readonly: false });
}

function getNextVillaCode(db: ReturnType<typeof getDb>): string {
  const row = db
    .prepare(
      "SELECT MAX(CAST(SUBSTR(villa_code, 4) AS INTEGER)) AS max_num FROM villas"
    )
    .get() as { max_num: number | null };
  const next = (row.max_num ?? 1000) + 1;
  return `MV-${next}`;
}

// GET /villas/stats  — must be registered before /villas/:id
router.get("/villas/stats", (req, res) => {
  const db = getDb();
  try {
    const total = (
      db.prepare("SELECT COUNT(*) as cnt FROM villas").get() as { cnt: number }
    ).cnt;
    const published = (
      db
        .prepare("SELECT COUNT(*) as cnt FROM villas WHERE status = 'published'")
        .get() as { cnt: number }
    ).cnt;
    const draft = (
      db
        .prepare("SELECT COUNT(*) as cnt FROM villas WHERE status = 'draft'")
        .get() as { cnt: number }
    ).cnt;
    const sold = (
      db
        .prepare("SELECT COUNT(*) as cnt FROM villas WHERE status = 'sold'")
        .get() as { cnt: number }
    ).cnt;
    const archived = (
      db
        .prepare("SELECT COUNT(*) as cnt FROM villas WHERE status = 'archived'")
        .get() as { cnt: number }
    ).cnt;

    const by_city = db
      .prepare(
        "SELECT city, COUNT(*) as count FROM villas WHERE city IS NOT NULL AND status != 'archived' GROUP BY city ORDER BY count DESC"
      )
      .all() as { city: string; count: number }[];

    const rows = db
      .prepare(
        "SELECT price FROM villas WHERE price IS NOT NULL AND status != 'archived'"
      )
      .all() as { price: number }[];

    const tiers: Record<string, number> = {
      اقتصادی: 0,
      متوسط: 0,
      "نیمه لوکس": 0,
      لوکس: 0,
    };
    for (const row of rows) {
      const p = row.price;
      if (p < 7_000_000_000) tiers["اقتصادی"]++;
      else if (p < 10_000_000_000) tiers["متوسط"]++;
      else if (p < 15_000_000_000) tiers["نیمه لوکس"]++;
      else tiers["لوکس"]++;
    }

    const by_price_tier = Object.entries(tiers).map(([tier, count]) => ({
      tier,
      count,
    }));

    res.json({ total, published, draft, sold, archived, by_city, by_price_tier });
  } finally {
    db.close();
  }
});

// GET /villas
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

    if (status) {
      query += " AND status = ?";
      params.push(status);
    }
    if (city) {
      query += " AND city = ?";
      params.push(city);
    }
    if (area_type) {
      query += " AND area_type = ?";
      params.push(area_type);
    }

    query += " ORDER BY created_at DESC";

    const rows = db.prepare(query).all(...params);
    res.json(rows);
  } finally {
    db.close();
  }
});

// POST /villas  — create
router.post("/villas", (req, res) => {
  const parsed = CreateVillaBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid request body", details: parsed.error.flatten() });
    return;
  }
  const data = parsed.data;

  const db = getDb();
  try {
    const villaCode = getNextVillaCode(db);

    db.prepare(`
      INSERT INTO villas (
        villa_code, city, area_type, price,
        land_size, building_size, bedrooms, master_bedrooms,
        is_townhouse, has_pool, has_jacuzzi, has_roof_garden,
        has_parking, has_storage,
        document_type, description,
        latitude, longitude, photos, video,
        status, created_at, updated_at
      ) VALUES (
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?,
        ?, ?,
        ?, ?, ?, ?,
        ?, datetime('now'), datetime('now')
      )
    `).run(
      villaCode,
      data.city ?? null,
      data.area_type ?? null,
      data.price ?? null,
      data.land_size ?? null,
      data.building_size ?? null,
      data.bedrooms ?? null,
      data.master_bedrooms ?? 0,
      data.is_townhouse ?? 0,
      data.has_pool ?? 0,
      data.has_jacuzzi ?? 0,
      data.has_roof_garden ?? 0,
      data.has_parking ?? 0,
      data.has_storage ?? 0,
      data.document_type ?? null,
      data.description ?? null,
      data.latitude ?? null,
      data.longitude ?? null,
      data.photos ?? null,
      data.video ?? null,
      data.status ?? "draft",
    );

    const created = db
      .prepare("SELECT * FROM villas WHERE villa_code = ?")
      .get(villaCode);
    res.status(201).json(created);
  } finally {
    db.close();
  }
});

// GET /villas/:id
router.get("/villas/:id", (req, res) => {
  const parsed = GetVillaParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const db = getDb();
  try {
    const row = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(parsed.data.id);
    if (!row) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }
    res.json(row);
  } finally {
    db.close();
  }
});

// PUT /villas/:id  — full update
router.put("/villas/:id", (req, res) => {
  const idParsed = UpdateVillaParams.safeParse({ id: Number(req.params.id) });
  const bodyParsed = UpdateVillaBody.safeParse(req.body);

  if (!idParsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }
  if (!bodyParsed.success) {
    res.status(400).json({ error: "Invalid request body", details: bodyParsed.error.flatten() });
    return;
  }

  const db = getDb();
  try {
    const existing = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(idParsed.data.id);
    if (!existing) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }

    const data = bodyParsed.data;
    db.prepare(`
      UPDATE villas SET
        city = ?, area_type = ?, price = ?,
        land_size = ?, building_size = ?, bedrooms = ?, master_bedrooms = ?,
        is_townhouse = ?, has_pool = ?, has_jacuzzi = ?,
        has_roof_garden = ?, has_parking = ?, has_storage = ?,
        document_type = ?, description = ?,
        latitude = ?, longitude = ?,
        photos = ?, video = ?,
        status = ?,
        updated_at = datetime('now')
      WHERE id = ?
    `).run(
      data.city ?? null,
      data.area_type ?? null,
      data.price ?? null,
      data.land_size ?? null,
      data.building_size ?? null,
      data.bedrooms ?? null,
      data.master_bedrooms ?? 0,
      data.is_townhouse ?? 0,
      data.has_pool ?? 0,
      data.has_jacuzzi ?? 0,
      data.has_roof_garden ?? 0,
      data.has_parking ?? 0,
      data.has_storage ?? 0,
      data.document_type ?? null,
      data.description ?? null,
      data.latitude ?? null,
      data.longitude ?? null,
      data.photos ?? null,
      data.video ?? null,
      data.status ?? "draft",
      idParsed.data.id,
    );

    const updated = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(idParsed.data.id);
    res.json(updated);
  } finally {
    db.close();
  }
});

// PATCH /villas/:id  — status-only update
router.patch("/villas/:id", (req, res) => {
  const idParsed = UpdateVillaStatusParams.safeParse({ id: Number(req.params.id) });
  const bodyParsed = UpdateVillaStatusBody.safeParse(req.body);

  if (!idParsed.success || !bodyParsed.success) {
    res.status(400).json({ error: "Invalid request" });
    return;
  }

  const db = getDb();
  try {
    const existing = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(idParsed.data.id);
    if (!existing) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }

    db.prepare(
      "UPDATE villas SET status = ?, updated_at = datetime('now') WHERE id = ?"
    ).run(bodyParsed.data.status, idParsed.data.id);

    const updated = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(idParsed.data.id);
    res.json(updated);
  } finally {
    db.close();
  }
});

// DELETE /villas/:id  — archive (never permanently deletes)
router.delete("/villas/:id", (req, res) => {
  const parsed = ArchiveVillaParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const db = getDb();
  try {
    const existing = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(parsed.data.id);
    if (!existing) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }

    db.prepare(
      "UPDATE villas SET status = 'archived', updated_at = datetime('now') WHERE id = ?"
    ).run(parsed.data.id);

    const archived = db
      .prepare("SELECT * FROM villas WHERE id = ?")
      .get(parsed.data.id);
    res.json(archived);
  } finally {
    db.close();
  }
});

export default router;
