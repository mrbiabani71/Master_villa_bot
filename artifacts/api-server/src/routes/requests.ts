import { Router, type IRouter } from "express";
import Database from "better-sqlite3";
import path from "path";
import {
  ListRequestsQueryParams,
  MarkRequestContactedParams,
  DeleteRequestParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

const DB_PATH = path.resolve(process.cwd(), "../../bot/bot.db");

function getDb() {
  return new Database(DB_PATH, { readonly: false });
}

router.get("/requests/stats", (_req, res) => {
  const db = getDb();
  try {
    const total = (db.prepare("SELECT COUNT(*) as cnt FROM visit_requests").get() as { cnt: number }).cnt;
    const pending = (db.prepare("SELECT COUNT(*) as cnt FROM visit_requests WHERE status = 'pending'").get() as { cnt: number }).cnt;
    const contacted = (db.prepare("SELECT COUNT(*) as cnt FROM visit_requests WHERE status = 'contacted'").get() as { cnt: number }).cnt;
    const visit_count = (db.prepare("SELECT COUNT(*) as cnt FROM visit_requests WHERE request_type = 'visit'").get() as { cnt: number }).cnt;
    const consultation_count = (db.prepare("SELECT COUNT(*) as cnt FROM visit_requests WHERE request_type = 'consultation'").get() as { cnt: number }).cnt;

    res.json({ total, pending, contacted, visit_count, consultation_count });
  } finally {
    db.close();
  }
});

const MAX_PAGE_SIZE = 100;
const DEFAULT_PAGE_SIZE = 20;

router.get("/requests", (req, res) => {
  const parsed = ListRequestsQueryParams.safeParse({
    ...req.query,
    page: req.query.page !== undefined ? Number(req.query.page) : 0,
    page_size:
      req.query.page_size !== undefined ? Number(req.query.page_size) : DEFAULT_PAGE_SIZE,
  });

  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query params" });
    return;
  }

  const { status, request_type } = parsed.data;
  const page = Math.max(0, parsed.data.page ?? 0);
  const page_size = Math.min(
    Math.max(1, parsed.data.page_size ?? DEFAULT_PAGE_SIZE),
    MAX_PAGE_SIZE
  );

  const db = getDb();
  try {
    let countQuery = "SELECT COUNT(*) as cnt FROM visit_requests r WHERE 1=1";
    let dataQuery = `
      SELECT r.id, r.villa_code, r.user_id, r.name, r.phone,
             r.area_type, r.request_type, r.status, r.created_at,
             v.price, v.city AS villa_city
      FROM visit_requests r
      LEFT JOIN villas v ON r.villa_code = v.villa_code
      WHERE 1=1
    `;
    const params: unknown[] = [];
    const countParams: unknown[] = [];

    if (status) {
      const cond = " AND r.status = ?";
      dataQuery += cond;
      countQuery += " AND r.status = ?";
      params.push(status);
      countParams.push(status);
    }
    if (request_type) {
      const cond = " AND r.request_type = ?";
      dataQuery += cond;
      countQuery += " AND r.request_type = ?";
      params.push(request_type);
      countParams.push(request_type);
    }

    dataQuery += " ORDER BY r.created_at DESC, r.id DESC LIMIT ? OFFSET ?";
    params.push(page_size, page * page_size);

    const total = (db.prepare(countQuery).get(...countParams) as { cnt: number }).cnt;
    const data = db.prepare(dataQuery).all(...params);

    res.json({ data, total, page, page_size });
  } finally {
    db.close();
  }
});

router.post("/requests/:id/contact", (req, res) => {
  const parsed = MarkRequestContactedParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const db = getDb();
  try {
    const existing = db.prepare("SELECT * FROM visit_requests WHERE id = ?").get(parsed.data.id);
    if (!existing) {
      res.status(404).json({ error: "Request not found" });
      return;
    }

    db.prepare("UPDATE visit_requests SET status = 'contacted' WHERE id = ?").run(parsed.data.id);

    const updated = db.prepare(`
      SELECT r.id, r.villa_code, r.user_id, r.name, r.phone,
             r.area_type, r.request_type, r.status, r.created_at,
             v.price, v.city AS villa_city
      FROM visit_requests r
      LEFT JOIN villas v ON r.villa_code = v.villa_code
      WHERE r.id = ?
    `).get(parsed.data.id);

    res.json(updated);
  } finally {
    db.close();
  }
});

router.delete("/requests/:id", (req, res) => {
  const parsed = DeleteRequestParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const db = getDb();
  try {
    db.prepare("DELETE FROM visit_requests WHERE id = ?").run(parsed.data.id);
    res.status(204).send();
  } finally {
    db.close();
  }
});

export default router;
