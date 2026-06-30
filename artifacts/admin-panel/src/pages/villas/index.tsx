import { useState } from "react";
import { useListVillas, useUpdateVillaStatus, getListVillasQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatTomans, formatDate } from "@/lib/format";
import { Link } from "wouter";
import { Search, Eye, Filter, Building, Trees, AlertCircle, ArrowRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export default function VillasPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [typeFilter, setTypeFilter] = useState<"all" | "ساحلی" | "جنگلی">("all");
  const [search, setSearch] = useState("");
  
  const queryClient = useQueryClient();

  const { data: villas, isLoading } = useListVillas({
    ...(statusFilter !== "all" && { status: statusFilter as "active" | "inactive" }),
    ...(typeFilter !== "all" && { area_type: typeFilter })
  });

  const updateStatus = useUpdateVillaStatus();

  const handleToggleStatus = (id: number, currentStatus: string) => {
    const newStatus = currentStatus === "active" ? "inactive" : "active";
    updateStatus.mutate(
      { id, data: { status: newStatus } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getListVillasQueryKey() });
        }
      }
    );
  };

  const filteredVillas = villas?.filter(v => 
    v.villa_code.toLowerCase().includes(search.toLowerCase()) || 
    (v.city && v.city.includes(search))
  );

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Properties Inventory</h2>
          <p className="text-muted-foreground mt-1">Manage and monitor your real estate portfolio</p>
        </div>
        <Button variant="default" className="gap-2" asChild>
          <a href={import.meta.env.VITE_BOT_URL || "#"} target="_blank" rel="noopener noreferrer">
            Open Bot <ArrowRight className="h-4 w-4" />
          </a>
        </Button>
      </div>

      <Card className="p-4 shadow-sm border-border bg-card">
        <div className="flex flex-col md:flex-row gap-4 items-end md:items-center">
          <div className="w-full md:w-72 space-y-1.5">
            <Label htmlFor="search" className="text-xs uppercase tracking-wider text-muted-foreground">Search</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                id="search"
                placeholder="Search by code or city..."
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          
          <div className="w-full md:w-48 space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Status</Label>
            <Select value={statusFilter} onValueChange={(v: any) => setStatusFilter(v)}>
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="active">Active Only</SelectItem>
                <SelectItem value="inactive">Inactive Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="w-full md:w-48 space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Area Type</Label>
            <Select value={typeFilter} onValueChange={(v: any) => setTypeFilter(v)}>
              <SelectTrigger>
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="ساحلی">Coastal (ساحلی)</SelectItem>
                <SelectItem value="جنگلی">Forest (جنگلی)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <Button variant="outline" className="w-full md:w-auto" onClick={() => {
            setSearch("");
            setStatusFilter("all");
            setTypeFilter("all");
          }}>
            <Filter className="h-4 w-4 mr-2" /> Clear
          </Button>
        </div>
      </Card>

      <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 items-center">
                <Skeleton className="h-12 w-full" />
              </div>
            ))}
          </div>
        ) : filteredVillas && filteredVillas.length > 0 ? (
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead className="w-[100px]">Code</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Specs</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredVillas.map((villa) => (
                <TableRow key={villa.id} className="group hover:bg-muted/30">
                  <TableCell className="font-mono font-medium text-primary">
                    <Link href={`/villas/${villa.id}`} className="hover:underline">{villa.villa_code}</Link>
                  </TableCell>
                  <TableCell dir="rtl" className="text-right">
                    {villa.city || "-"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {villa.area_type === 'ساحلی' ? (
                        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800">
                          <Building className="h-3 w-3 mr-1" /> Coastal
                        </Badge>
                      ) : villa.area_type === 'جنگلی' ? (
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800">
                          <Trees className="h-3 w-3 mr-1" /> Forest
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="font-medium text-emerald-600 dark:text-emerald-400" dir="rtl">
                    {formatTomans(villa.price)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {villa.land_size}m² / {villa.building_size}m²
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Switch 
                        checked={villa.status === 'active'}
                        onCheckedChange={() => handleToggleStatus(villa.id, villa.status)}
                        disabled={updateStatus.isPending}
                        className="data-[state=checked]:bg-emerald-500"
                      />
                      <span className="text-xs uppercase font-medium tracking-wider text-muted-foreground w-16">
                        {villa.status}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" asChild className="hover:bg-primary/10 hover:text-primary">
                      <Link href={`/villas/${villa.id}`}>
                        <Eye className="h-4 w-4" />
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="p-12 text-center flex flex-col items-center justify-center">
            <AlertCircle className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
            <h3 className="text-lg font-medium">No villas found</h3>
            <p className="text-muted-foreground mt-1 max-w-sm">
              We couldn't find any properties matching your current filters. Try adjusting your search criteria.
            </p>
            <Button variant="outline" className="mt-6" onClick={() => {
              setSearch("");
              setStatusFilter("all");
              setTypeFilter("all");
            }}>
              Clear Filters
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
