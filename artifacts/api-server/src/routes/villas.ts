import { Router, type IRouter } from "express";
import { db, villasTable } from "@workspace/db";
import { eq, sql } from "drizzle-orm";
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

const MAX_PAGE_SIZE = 100;
const DEFAULT_PAGE_SIZE = 20;

async function getNextVillaCode(): Promise<string> {
  // The regex is passed as a parameter so the literal '$' never appears as a
  // raw character inside the tagged-template string — esbuild misparses a
  // bare '$' immediately before the closing backtick of a tagged template.
  const mvPattern = "^MV-[0-9]+$";
  const result = await db.execute(
    sql`SELECT MAX(
          CASE WHEN villa_code ~ ${mvPattern}
          THEN CAST(SUBSTRING(villa_code, 4) AS INTEGER)
          END
        ) AS max_num FROM villas`
  );
  const maxNum = (result.rows[0] as { max_num: number | null }).max_num;
  const next = (maxNum ?? 1000) + 1;
  return `MV-${next}`;
}

router.get("/villas/stats", async (_req, res) => {
  try {
    const [total, published, draft, sold, archived, byCity, priceRows] = await Promise.all([
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas WHERE status = 'published'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas WHERE status = 'draft'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas WHERE status = 'sold'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas WHERE status = 'archived'`),
      db.execute(sql`SELECT city, COUNT(*) as count FROM villas WHERE city IS NOT NULL AND status != 'archived' GROUP BY city ORDER BY count DESC`),
      db.execute(sql`SELECT price FROM villas WHERE price IS NOT NULL AND status != 'archived'`),
    ]);

    const tiers: Record<string, number> = { اقتصادی: 0, متوسط: 0, "نیمه لوکس": 0, لوکس: 0 };
    for (const row of priceRows.rows as { price: number }[]) {
      const p = row.price;
      if (p < 7_000_000_000) tiers["اقتصادی"]++;
      else if (p < 10_000_000_000) tiers["متوسط"]++;
      else if (p < 15_000_000_000) tiers["نیمه لوکس"]++;
      else tiers["لوکس"]++;
    }

    const by_price_tier = Object.entries(tiers).map(([tier, count]) => ({ tier, count }));

    res.json({
      total: Number((total.rows[0] as { cnt: string }).cnt),
      published: Number((published.rows[0] as { cnt: string }).cnt),
      draft: Number((draft.rows[0] as { cnt: string }).cnt),
      sold: Number((sold.rows[0] as { cnt: string }).cnt),
      archived: Number((archived.rows[0] as { cnt: string }).cnt),
      by_city: byCity.rows,
      by_price_tier,
    });
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/villas", async (req, res) => {
  const parsed = ListVillasQueryParams.safeParse({
    ...req.query,
    page: req.query.page !== undefined ? Number(req.query.page) : 0,
    page_size: req.query.page_size !== undefined ? Number(req.query.page_size) : DEFAULT_PAGE_SIZE,
  });

  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query params" });
    return;
  }
  const { status, city, area_type, page, page_size } = parsed.data;
  const safePage = Math.max(0, page ?? 0);
  const safePageSize = Math.min(Math.max(1, page_size ?? DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE);

  try {
    let conditions = sql`1=1`;
    if (status) conditions = sql`${conditions} AND status = ${status}`;
    if (city) conditions = sql`${conditions} AND city = ${city}`;
    if (area_type) conditions = sql`${conditions} AND area_type = ${area_type}`;

    const [countResult, rows] = await Promise.all([
      db.execute(sql`SELECT COUNT(*) as cnt FROM villas WHERE ${conditions}`),
      db.execute(sql`SELECT * FROM villas WHERE ${conditions} ORDER BY created_at DESC LIMIT ${safePageSize} OFFSET ${safePage * safePageSize}`),
    ]);

    const total = Number((countResult.rows[0] as { cnt: string }).cnt);
    res.json({ data: rows.rows, total, page: safePage, page_size: safePageSize });
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/villas", async (req, res) => {
  const parsed = CreateVillaBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid request body", details: parsed.error.flatten() });
    return;
  }
  const data = parsed.data;

  try {
    const villaCode = data.villa_code?.trim() || await getNextVillaCode();

    // If caller supplied an explicit code, reject it early if it already exists.
    if (data.villa_code?.trim()) {
      const [existing] = await db
        .select({ id: villasTable.id })
        .from(villasTable)
        .where(eq(villasTable.villa_code, villaCode));
      if (existing) {
        res.status(409).json({ error: `Villa code '${villaCode}' already exists` });
        return;
      }
    }

    const [created] = await db.insert(villasTable).values({
      villa_code: villaCode,
      city: data.city ?? null,
      area_type: data.area_type ?? null,
      price: data.price ?? null,
      land_size: data.land_size ?? null,
      building_size: data.building_size ?? null,
      bedrooms: data.bedrooms ?? null,
      master_bedrooms: data.master_bedrooms ?? 0,
      is_townhouse: data.is_townhouse ?? 0,
      has_pool: data.has_pool ?? 0,
      has_jacuzzi: data.has_jacuzzi ?? 0,
      has_roof_garden: data.has_roof_garden ?? 0,
      has_parking: data.has_parking ?? 0,
      has_storage: data.has_storage ?? 0,
      document_type: data.document_type ?? null,
      description: data.description ?? null,
      latitude: data.latitude ?? null,
      longitude: data.longitude ?? null,
      photos: data.photos ?? null,
      video: data.video ?? null,
      status: data.status ?? "draft",
    }).returning();
    res.status(201).json(created);
  } catch (err: unknown) {
    // PostgreSQL unique-constraint violation (code 23505) — catches the race
    // where two concurrent requests with the same explicit code both pass the
    // pre-check above, but only one INSERT succeeds.
    if (
      err !== null &&
      typeof err === "object" &&
      "code" in err &&
      (err as { code: string }).code === "23505"
    ) {
      res.status(409).json({ error: `Villa code '${villaCode}' already exists` });
      return;
    }
    res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/villas/:id", async (req, res) => {
  const parsed = GetVillaParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  try {
    const [row] = await db.select().from(villasTable).where(eq(villasTable.id, parsed.data.id));
    if (!row) {
      res.status(404).json({ error: "Villa not found" });
      return;
    }
    res.json(row);
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.put("/villas/:id", async (req, res) => {
  const idParsed = UpdateVillaParams.safeParse({ id: Number(req.params.id) });
  const bodyParsed = UpdateVillaBody.safeParse(req.body);

  if (!idParsed.success) { res.status(400).json({ error: "Invalid id" }); return; }
  if (!bodyParsed.success) { res.status(400).json({ error: "Invalid request body", details: bodyParsed.error.flatten() }); return; }

  try {
    const existing = await db.select().from(villasTable).where(eq(villasTable.id, idParsed.data.id));
    if (!existing.length) { res.status(404).json({ error: "Villa not found" }); return; }

    const data = bodyParsed.data;
    const [updated] = await db.update(villasTable).set({
      city: data.city ?? null,
      area_type: data.area_type ?? null,
      price: data.price ?? null,
      land_size: data.land_size ?? null,
      building_size: data.building_size ?? null,
      bedrooms: data.bedrooms ?? null,
      master_bedrooms: data.master_bedrooms ?? 0,
      is_townhouse: data.is_townhouse ?? 0,
      has_pool: data.has_pool ?? 0,
      has_jacuzzi: data.has_jacuzzi ?? 0,
      has_roof_garden: data.has_roof_garden ?? 0,
      has_parking: data.has_parking ?? 0,
      has_storage: data.has_storage ?? 0,
      document_type: data.document_type ?? null,
      description: data.description ?? null,
      latitude: data.latitude ?? null,
      longitude: data.longitude ?? null,
      photos: data.photos ?? null,
      video: data.video ?? null,
      status: data.status ?? "draft",
      updated_at: new Date(),
    }).where(eq(villasTable.id, idParsed.data.id)).returning();
    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.patch("/villas/:id", async (req, res) => {
  const idParsed = UpdateVillaStatusParams.safeParse({ id: Number(req.params.id) });
  const bodyParsed = UpdateVillaStatusBody.safeParse(req.body);

  if (!idParsed.success || !bodyParsed.success) {
    res.status(400).json({ error: "Invalid request" });
    return;
  }

  try {
    const existing = await db.select().from(villasTable).where(eq(villasTable.id, idParsed.data.id));
    if (!existing.length) { res.status(404).json({ error: "Villa not found" }); return; }

    const [updated] = await db.update(villasTable)
      .set({ status: bodyParsed.data.status, updated_at: new Date() })
      .where(eq(villasTable.id, idParsed.data.id))
      .returning();
    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/villas/:id", async (req, res) => {
  const parsed = ArchiveVillaParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  try {
    const existing = await db.select().from(villasTable).where(eq(villasTable.id, parsed.data.id));
    if (!existing.length) { res.status(404).json({ error: "Villa not found" }); return; }

    const [archived] = await db.update(villasTable)
      .set({ status: "archived", updated_at: new Date() })
      .where(eq(villasTable.id, parsed.data.id))
      .returning();
    res.json(archived);
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
