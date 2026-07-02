import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { VillaStatus } from "@/lib/villa-status";

const CITIES = ["محمودآباد", "سرخرود", "ایزدشهر", "نور", "آمل", "چمستان"];
const AREA_TYPES = ["ساحلی", "جنگلی"];
const DOC_TYPES = [
  "سند تک‌برگ",
  "سند منگوله‌دار",
  "وکالتنامه",
  "قولنامه",
  "بنچاق",
];

export interface VillaFormValues {
  city: string;
  area_type: string;
  price: string;
  land_size: string;
  building_size: string;
  bedrooms: string;
  master_bedrooms: string;
  is_townhouse: boolean;
  has_pool: boolean;
  has_jacuzzi: boolean;
  has_roof_garden: boolean;
  has_parking: boolean;
  has_storage: boolean;
  document_type: string;
  description: string;
  latitude: string;
  longitude: string;
  photos: string;
  video: string;
  status: VillaStatus;
}

export const EMPTY_FORM: VillaFormValues = {
  city: "",
  area_type: "",
  price: "",
  land_size: "",
  building_size: "",
  bedrooms: "",
  master_bedrooms: "",
  is_townhouse: false,
  has_pool: false,
  has_jacuzzi: false,
  has_roof_garden: false,
  has_parking: false,
  has_storage: false,
  document_type: "",
  description: "",
  latitude: "",
  longitude: "",
  photos: "",
  video: "",
  status: "draft",
};

export function formValuesToApiData(v: VillaFormValues) {
  return {
    city: v.city || null,
    area_type: v.area_type || null,
    price: v.price ? parseFloat(v.price) : null,
    land_size: v.land_size ? parseFloat(v.land_size) : null,
    building_size: v.building_size ? parseFloat(v.building_size) : null,
    bedrooms: v.bedrooms ? parseInt(v.bedrooms, 10) : null,
    master_bedrooms: v.master_bedrooms ? parseInt(v.master_bedrooms, 10) : 0,
    is_townhouse: v.is_townhouse ? 1 : 0,
    has_pool: v.has_pool ? 1 : 0,
    has_jacuzzi: v.has_jacuzzi ? 1 : 0,
    has_roof_garden: v.has_roof_garden ? 1 : 0,
    has_parking: v.has_parking ? 1 : 0,
    has_storage: v.has_storage ? 1 : 0,
    document_type: v.document_type || null,
    description: v.description || null,
    latitude: v.latitude ? parseFloat(v.latitude) : null,
    longitude: v.longitude ? parseFloat(v.longitude) : null,
    photos: v.photos || null,
    video: v.video || null,
    status: v.status,
  };
}

interface VillaFormProps {
  initialValues?: Partial<VillaFormValues>;
  onSubmit: (values: VillaFormValues) => void;
  isLoading?: boolean;
  mode: "create" | "edit";
  onCancel: () => void;
}

export function VillaForm({
  initialValues,
  onSubmit,
  isLoading,
  mode,
  onCancel,
}: VillaFormProps) {
  const [values, setValues] = useState<VillaFormValues>({
    ...EMPTY_FORM,
    ...initialValues,
  });

  const set = (field: keyof VillaFormValues, value: string | boolean) =>
    setValues((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-sm">
          <CardHeader className="bg-muted/30 pb-3">
            <CardTitle className="text-base">Location & Classification</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <div className="space-y-1.5">
              <Label>City</Label>
              <Select value={values.city} onValueChange={(v) => set("city", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select city..." />
                </SelectTrigger>
                <SelectContent>
                  {CITIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      <span dir="rtl">{c}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Area Type</Label>
              <Select
                value={values.area_type}
                onValueChange={(v) => set("area_type", v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select area type..." />
                </SelectTrigger>
                <SelectContent>
                  {AREA_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      <span dir="rtl">{t}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Document Type</Label>
              <Select
                value={values.document_type}
                onValueChange={(v) => set("document_type", v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select document type..." />
                </SelectTrigger>
                <SelectContent>
                  {DOC_TYPES.map((d) => (
                    <SelectItem key={d} value={d}>
                      <span dir="rtl">{d}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select
                value={values.status}
                onValueChange={(v) => set("status", v as VillaStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="published">Published</SelectItem>
                  <SelectItem value="sold">Sold</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="bg-muted/30 pb-3">
            <CardTitle className="text-base">Pricing & Specifications</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="price">Price (Rials)</Label>
              <Input
                id="price"
                type="number"
                min="0"
                placeholder="e.g. 6500000000"
                value={values.price}
                onChange={(e) => set("price", e.target.value)}
              />
              {values.price && (
                <p className="text-xs text-muted-foreground">
                  ≈ {(parseFloat(values.price) / 1_000_000_000).toFixed(2)} billion Rials
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="land_size">Land Size (m²)</Label>
                <Input
                  id="land_size"
                  type="number"
                  min="0"
                  placeholder="e.g. 500"
                  value={values.land_size}
                  onChange={(e) => set("land_size", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="building_size">Building Size (m²)</Label>
                <Input
                  id="building_size"
                  type="number"
                  min="0"
                  placeholder="e.g. 200"
                  value={values.building_size}
                  onChange={(e) => set("building_size", e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="bedrooms">Bedrooms</Label>
                <Input
                  id="bedrooms"
                  type="number"
                  min="0"
                  placeholder="e.g. 3"
                  value={values.bedrooms}
                  onChange={(e) => set("bedrooms", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="master_bedrooms">Master Bedrooms</Label>
                <Input
                  id="master_bedrooms"
                  type="number"
                  min="0"
                  placeholder="e.g. 1"
                  value={values.master_bedrooms}
                  onChange={(e) => set("master_bedrooms", e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="latitude">Latitude</Label>
                <Input
                  id="latitude"
                  type="number"
                  step="any"
                  placeholder="e.g. 36.6"
                  value={values.latitude}
                  onChange={(e) => set("latitude", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="longitude">Longitude</Label>
                <Input
                  id="longitude"
                  type="number"
                  step="any"
                  placeholder="e.g. 52.2"
                  value={values.longitude}
                  onChange={(e) => set("longitude", e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="bg-muted/30 pb-3">
            <CardTitle className="text-base">Amenities & Features</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="grid grid-cols-2 gap-4">
              {(
                [
                  { key: "is_townhouse", label: "Townhouse" },
                  { key: "has_pool", label: "Pool" },
                  { key: "has_jacuzzi", label: "Jacuzzi" },
                  { key: "has_roof_garden", label: "Roof Garden" },
                  { key: "has_parking", label: "Parking" },
                  { key: "has_storage", label: "Storage" },
                ] as { key: keyof VillaFormValues; label: string }[]
              ).map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2">
                  <Checkbox
                    id={key}
                    checked={values[key] as boolean}
                    onCheckedChange={(checked) => set(key, Boolean(checked))}
                  />
                  <Label htmlFor={key} className="cursor-pointer font-normal">
                    {label}
                  </Label>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="bg-muted/30 pb-3">
            <CardTitle className="text-base">Media & Description</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="photos">Photos (Telegram File IDs)</Label>
              <Input
                id="photos"
                placeholder="Comma-separated Telegram file IDs"
                value={values.photos}
                onChange={(e) => set("photos", e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Managed via Telegram bot. Paste file IDs here if needed.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="video">Video (Telegram File ID)</Label>
              <Input
                id="video"
                placeholder="Telegram video file ID"
                value={values.video}
                onChange={(e) => set("video", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Property description..."
                rows={4}
                dir="rtl"
                value={values.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <Separator />

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading
            ? mode === "create"
              ? "Creating..."
              : "Saving..."
            : mode === "create"
            ? "Create Villa"
            : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
