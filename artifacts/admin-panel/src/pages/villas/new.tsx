import { useCreateVilla, getListVillasQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, Link } from "wouter";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { VillaForm, formValuesToApiData, type VillaFormValues } from "@/components/villa-form";
import { useToast } from "@/hooks/use-toast";

export default function VillaNew() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createVilla = useCreateVilla({
    mutation: {
      onSuccess: (villa) => {
        queryClient.invalidateQueries({ queryKey: getListVillasQueryKey() });
        toast({ title: "Villa created", description: `${villa.villa_code} has been added.` });
        navigate(`/villas/${villa.id}`);
      },
      onError: () => {
        toast({ title: "Error", description: "Failed to create villa.", variant: "destructive" });
      },
    },
  });

  const handleSubmit = (values: VillaFormValues) => {
    createVilla.mutate({ data: formValuesToApiData(values) });
  };

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-6xl mx-auto">
      <Button
        variant="ghost"
        className="pl-0 gap-2 text-muted-foreground hover:text-foreground"
        asChild
      >
        <Link href="/villas">
          <ArrowLeft className="h-4 w-4" /> Back to Inventory
        </Link>
      </Button>

      <div>
        <h2 className="text-3xl font-bold tracking-tight">Add New Villa</h2>
        <p className="text-muted-foreground mt-1">
          A villa code will be auto-generated. Status defaults to Draft.
        </p>
      </div>

      <VillaForm
        mode="create"
        onSubmit={handleSubmit}
        isLoading={createVilla.isPending}
        onCancel={() => navigate("/villas")}
      />
    </div>
  );
}
