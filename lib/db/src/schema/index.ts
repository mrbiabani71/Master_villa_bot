import { pgTable, serial, text, real, integer, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const villasTable = pgTable("villas", {
  id: serial("id").primaryKey(),
  villa_code: text("villa_code").unique().notNull(),
  city: text("city"),
  area_type: text("area_type"),
  price: real("price"),
  land_size: real("land_size"),
  building_size: real("building_size"),
  bedrooms: integer("bedrooms"),
  master_bedrooms: integer("master_bedrooms").default(0),
  is_townhouse: integer("is_townhouse").notNull().default(0),
  has_pool: integer("has_pool").notNull().default(0),
  has_jacuzzi: integer("has_jacuzzi").notNull().default(0),
  has_roof_garden: integer("has_roof_garden").notNull().default(0),
  has_parking: integer("has_parking").notNull().default(0),
  has_storage: integer("has_storage").notNull().default(0),
  document_type: text("document_type"),
  description: text("description"),
  latitude: real("latitude"),
  longitude: real("longitude"),
  photos: text("photos"),
  video: text("video"),
  status: text("status").notNull().default("draft"),
  created_at: timestamp("created_at", { withTimezone: false }).defaultNow().notNull(),
  updated_at: timestamp("updated_at", { withTimezone: false }).defaultNow().notNull(),
});

export const visitRequestsTable = pgTable("visit_requests", {
  id: serial("id").primaryKey(),
  villa_code: text("villa_code").notNull(),
  user_id: integer("user_id").notNull(),
  name: text("name").notNull(),
  phone: text("phone").notNull(),
  area_type: text("area_type").default(""),
  request_type: text("request_type").default("visit"),
  status: text("status").default("pending"),
  created_at: timestamp("created_at", { withTimezone: false }).defaultNow().notNull(),
});

export const insertVillaSchema = createInsertSchema(villasTable).omit({ id: true, created_at: true, updated_at: true });
export type InsertVilla = z.infer<typeof insertVillaSchema>;
export type Villa = typeof villasTable.$inferSelect;

export const insertVisitRequestSchema = createInsertSchema(visitRequestsTable).omit({ id: true, created_at: true });
export type InsertVisitRequest = z.infer<typeof insertVisitRequestSchema>;
export type VisitRequest = typeof visitRequestsTable.$inferSelect;
