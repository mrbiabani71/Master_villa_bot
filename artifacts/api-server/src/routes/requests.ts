import { Router, type IRouter } from "express";
import { db, visitRequestsTable, villasTable } from "@workspace/db";
import { eq, sql } from "drizzle-orm";
import {
  ListRequestsQueryParams,
  MarkRequestContactedParams,
  DeleteRequestParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

const MAX_PAGE_SIZE = 100;
const DEFAULT_PAGE_SIZE = 20;

router.get("/requests/stats", async (_req, res) => {
  try {
    const [total, pending, contacted, visitCount, consultCount] = await Promise.all([
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests WHERE status = 'pending'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests WHERE status = 'contacted'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests WHERE request_type = 'visit'`),
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests WHERE request_type = 'consultation'`),
    ]);

    res.json({
      total: Number((total.rows[0] as { cnt: string }).cnt),
      pending: Number((pending.rows[0] as { cnt: string }).cnt),
      contacted: Number((contacted.rows[0] as { cnt: string }).cnt),
      visit_count: Number((visitCount.rows[0] as { cnt: string }).cnt),
      consultation_count: Number((consultCount.rows[0] as { cnt: string }).cnt),
    });
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/requests", async (req, res) => {
  const parsed = ListRequestsQueryParams.safeParse({
    ...req.query,
    page: req.query.page !== undefined ? Number(req.query.page) : 0,
    page_size: req.query.page_size !== undefined ? Number(req.query.page_size) : DEFAULT_PAGE_SIZE,
  });

  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query params" });
    return;
  }

  const { status, request_type } = parsed.data;
  const page = Math.max(0, parsed.data.page ?? 0);
  const page_size = Math.min(Math.max(1, parsed.data.page_size ?? DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE);

  try {
    let conditions = sql`1=1`;
    if (status) conditions = sql`${conditions} AND r.status = ${status}`;
    if (request_type) conditions = sql`${conditions} AND r.request_type = ${request_type}`;

    const [countResult, rows] = await Promise.all([
      db.execute(sql`SELECT COUNT(*) as cnt FROM visit_requests r WHERE ${conditions}`),
      db.execute(sql`
        SELECT r.id, r.villa_code, r.user_id, r.name, r.phone,
               r.area_type, r.request_type, r.status, r.created_at,
               v.price, v.city AS villa_city
        FROM visit_requests r
        LEFT JOIN villas v ON r.villa_code = v.villa_code
        WHERE ${conditions}
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT ${page_size} OFFSET ${page * page_size}
      `),
    ]);

    const total = Number((countResult.rows[0] as { cnt: string }).cnt);
    res.json({ data: rows.rows, total, page, page_size });
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/requests/:id/contact", async (req, res) => {
  const parsed = MarkRequestContactedParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  try {
    const existing = await db.select().from(visitRequestsTable).where(eq(visitRequestsTable.id, parsed.data.id));
    if (!existing.length) { res.status(404).json({ error: "Request not found" }); return; }

    await db.update(visitRequestsTable).set({ status: "contacted" }).where(eq(visitRequestsTable.id, parsed.data.id));

    const [updated] = await db.execute(sql`
      SELECT r.id, r.villa_code, r.user_id, r.name, r.phone,
             r.area_type, r.request_type, r.status, r.created_at,
             v.price, v.city AS villa_city
      FROM visit_requests r
      LEFT JOIN villas v ON r.villa_code = v.villa_code
      WHERE r.id = ${parsed.data.id}
    `).then(r => r.rows);

    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/requests/:id", async (req, res) => {
  const parsed = DeleteRequestParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  try {
    await db.delete(visitRequestsTable).where(eq(visitRequestsTable.id, parsed.data.id));
    res.status(204).send();
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
