import { useGetVilla, useUpdateVilla, getListVillasQueryKey, getVilla } from "@workspace/api-client-react";
import { useParams, useLocation, Link } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft } from "lucide-react";
import { VillaForm, formValuesToApiData, type VillaFormValues } from "@/components/villa-form";
import { useToast } from "@/hooks/use-toast";
import type { VillaStatus } from "@/lib/villa-status";

type Villa = Awaited<ReturnType<typeof getVilla>>;

function villaToFormValues(villa: Villa): VillaFormValues {
  return {
    city: villa.city ?? "",
    area_type: villa.area_type ?? "",
    price: villa.price != null ? String(villa.price) : "",
    land_size: villa.land_size != null ? String(villa.land_size) : "",
    building_size: villa.building_size != null ? String(villa.building_size) : "",
    bedrooms: villa.bedrooms != null ? String(villa.bedrooms) : "",
    master_bedrooms: villa.master_bedrooms != null ? String(villa.master_bedrooms) : "",
    is_townhouse: Boolean(villa.is_townhouse),
    has_pool: Boolean(villa.has_pool),
    has_jacuzzi: Boolean(villa.has_jacuzzi),
    has_roof_garden: Boolean(villa.has_roof_garden),
    has_parking: Boolean(villa.has_parking),
    has_storage: Boolean(villa.has_storage),
    document_type: villa.document_type ?? "",
    description: villa.description ?? "",
    latitude: villa.latitude != null ? String(villa.latitude) : "",
    longitude: villa.longitude != null ? String(villa.longitude) : "",
    photos: villa.photos ?? "",
    video: villa.video ?? "",
    status: (villa.status as VillaStatus) ?? "draft",
  };
}

export default function VillaEdit() {
  const { id } = useParams<{ id: string }>();
  const villaId = parseInt(id, 10);
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: villa, isLoading, error } = useGetVilla(villaId, {
    query: { enabled: !isNaN(villaId), queryKey: [villaId] },
  });

  const updateVilla = useUpdateVilla({
    mutation: {
      onSuccess: (updated) => {
        queryClient.invalidateQueries({ queryKey: getListVillasQueryKey() });
        toast({ title: "Villa updated", description: `${updated.villa_code} has been saved.` });
        navigate(`/villas/${villaId}`);
      },
      onError: () => {
        toast({ title: "Error", description: "Failed to update villa.", variant: "destructive" });
      },
    },
  });

  const handleSubmit = (values: VillaFormValues) => {
    updateVilla.mutate({ id: villaId, data: formValuesToApiData(values) });
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 max-w-6xl mx-auto">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-12 w-64" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (error || !villa) {
    return (
      <div className="p-8 text-center max-w-2xl mx-auto mt-20">
        <h2 className="text-2xl font-bold text-destructive mb-2">Villa Not Found</h2>
        <Button asChild>
          <Link href="/villas">Back to Inventory</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-6xl mx-auto">
      <Button
        variant="ghost"
        className="pl-0 gap-2 text-muted-foreground hover:text-foreground"
        asChild
      >
        <Link href={`/villas/${villaId}`}>
          <ArrowLeft className="h-4 w-4" /> Back to {villa.villa_code}
        </Link>
      </Button>

      <div>
        <h2 className="text-3xl font-bold tracking-tight">Edit Villa</h2>
        <p className="text-muted-foreground mt-1">
          Code: <span className="font-mono font-medium text-primary">{villa.villa_code}</span>
          {" "}— Villa codes are permanent and cannot be changed.
        </p>
      </div>

      <VillaForm
        mode="edit"
        initialValues={villaToFormValues(villa)}
        onSubmit={handleSubmit}
        isLoading={updateVilla.isPending}
        onCancel={() => navigate(`/villas/${villaId}`)}
      />
    </div>
  );
}
