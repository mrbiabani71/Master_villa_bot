import { useGetVilla } from "@workspace/api-client-react";
import { useParams, Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatTomans, formatDate } from "@/lib/format";
import { 
  ArrowLeft, MapPin, Building2, Trees, Ruler, BedDouble, 
  CarFront, Waves, Droplets, SunMedium, Package, FileText, Calendar 
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";

export default function VillaDetail() {
  const { id } = useParams<{ id: string }>();
  const villaId = parseInt(id, 10);

  const { data: villa, isLoading, error } = useGetVilla(villaId, {
    query: {
      enabled: !isNaN(villaId),
      queryKey: [villaId],
    }
  });

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 max-w-5xl mx-auto">
        <Skeleton className="h-8 w-24" />
        <div className="space-y-4">
          <Skeleton className="h-12 w-[300px]" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton className="h-[400px] md:col-span-2" />
            <Skeleton className="h-[400px]" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !villa) {
    return (
      <div className="p-8 text-center max-w-2xl mx-auto mt-20">
        <h2 className="text-2xl font-bold text-destructive mb-2">Property Not Found</h2>
        <p className="text-muted-foreground mb-6">The villa you are looking for does not exist or an error occurred.</p>
        <Button asChild>
          <Link href="/villas">Back to Properties</Link>
        </Button>
      </div>
    );
  }

  const photos = villa.photos ? villa.photos.split(',') : [];

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-6xl mx-auto">
      <Button variant="ghost" className="pl-0 gap-2 text-muted-foreground hover:text-foreground" asChild>
        <Link href="/villas">
          <ArrowLeft className="h-4 w-4" /> Back to Inventory
        </Link>
      </Button>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Badge className={villa.status === 'active' ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-muted text-muted-foreground hover:bg-muted'}>
              {villa.status.toUpperCase()}
            </Badge>
            <span className="font-mono text-xl font-bold text-primary">{villa.villa_code}</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight flex items-center gap-2">
            <MapPin className="h-7 w-7 text-muted-foreground" />
            <span dir="rtl">{villa.city}</span>
          </h1>
        </div>
        <div className="text-right">
          <p className="text-sm uppercase tracking-wider text-muted-foreground font-semibold mb-1">Asking Price</p>
          <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400" dir="rtl">
            {formatTomans(villa.price)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="overflow-hidden shadow-sm">
            <div className="bg-muted aspect-video relative flex items-center justify-center border-b">
              {photos.length > 0 ? (
                <div className="absolute inset-0 flex items-center justify-center bg-zinc-900">
                  <span className="text-zinc-50 font-medium">Image preview not available in admin context</span>
                  <div className="absolute bottom-4 right-4 bg-black/60 text-white text-xs px-3 py-1.5 rounded-full backdrop-blur-md">
                    {photos.length} Photos Attached
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground flex flex-col items-center">
                  <Building2 className="h-12 w-12 mb-2 opacity-20" />
                  <p>No photos available</p>
                </div>
              )}
            </div>
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-4">Property Description</h3>
              <p className="text-foreground/80 leading-relaxed whitespace-pre-wrap font-medium" dir="rtl">
                {villa.description || "No description provided."}
              </p>
              
              {villa.latitude && villa.longitude && (
                <div className="mt-6">
                  <Button variant="outline" className="w-full gap-2" asChild>
                    <a href={`https://www.google.com/maps?q=${villa.latitude},${villa.longitude}`} target="_blank" rel="noopener noreferrer">
                      <MapPin className="h-4 w-4 text-blue-500" /> View on Google Maps
                    </a>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="bg-muted/30 pb-4">
              <CardTitle className="text-lg">Key Specifications</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y">
                <div className="flex justify-between items-center p-4">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <Ruler className="h-4 w-4" />
                    <span className="text-sm">Land Area</span>
                  </div>
                  <span className="font-semibold">{villa.land_size ? `${villa.land_size} m²` : '-'}</span>
                </div>
                <div className="flex justify-between items-center p-4">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <Building2 className="h-4 w-4" />
                    <span className="text-sm">Built Area</span>
                  </div>
                  <span className="font-semibold">{villa.building_size ? `${villa.building_size} m²` : '-'}</span>
                </div>
                <div className="flex justify-between items-center p-4">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <BedDouble className="h-4 w-4" />
                    <span className="text-sm">Bedrooms</span>
                  </div>
                  <span className="font-semibold">{villa.bedrooms || '-'}</span>
                </div>
                <div className="flex justify-between items-center p-4">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    {villa.area_type === 'ساحلی' ? <Waves className="h-4 w-4 text-blue-500" /> : <Trees className="h-4 w-4 text-green-500" />}
                    <span className="text-sm">Area Type</span>
                  </div>
                  <span className="font-semibold" dir="rtl">{villa.area_type || '-'}</span>
                </div>
                <div className="flex justify-between items-center p-4">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <FileText className="h-4 w-4" />
                    <span className="text-sm">Document</span>
                  </div>
                  <span className="font-semibold" dir="rtl">{villa.document_type || '-'}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader className="bg-muted/30 pb-4">
              <CardTitle className="text-lg">Amenities & Features</CardTitle>
            </CardHeader>
            <CardContent className="p-4 grid grid-cols-2 gap-4">
              <div className={`flex items-center gap-2 text-sm ${villa.has_pool ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <Waves className="h-4 w-4" /> Pool
              </div>
              <div className={`flex items-center gap-2 text-sm ${villa.has_jacuzzi ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <Droplets className="h-4 w-4" /> Jacuzzi
              </div>
              <div className={`flex items-center gap-2 text-sm ${villa.has_roof_garden ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <SunMedium className="h-4 w-4" /> Roof Garden
              </div>
              <div className={`flex items-center gap-2 text-sm ${villa.has_parking ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <CarFront className="h-4 w-4" /> Parking
              </div>
              <div className={`flex items-center gap-2 text-sm ${villa.has_storage ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <Package className="h-4 w-4" /> Storage
              </div>
              <div className={`flex items-center gap-2 text-sm ${villa.is_townhouse ? 'text-foreground font-medium' : 'text-muted-foreground/50 line-through'}`}>
                <Building2 className="h-4 w-4" /> Townhouse
              </div>
            </CardContent>
          </Card>

          <Card className="shadow-sm bg-muted/20">
            <CardContent className="p-4 flex items-center justify-between text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4" /> Listed On
              </div>
              <span>{formatDate(villa.created_at)}</span>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
