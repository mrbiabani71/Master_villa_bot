import { useState } from "react";
import { useListRequests, useMarkRequestContacted, useDeleteRequest, getListRequestsQueryKey, getGetRequestStatsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatTomans, formatDate } from "@/lib/format";
import { CheckCircle2, Trash2, Phone, Search, Filter, MessageSquare, AlertCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Link } from "wouter";

export default function RequestsPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "contacted">("all");
  const [typeFilter, setTypeFilter] = useState<"all" | "visit" | "consultation">("all");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: requestsPage, isLoading } = useListRequests({
    page,
    page_size: pageSize,
    ...(statusFilter !== "all" && { status: statusFilter as "pending" | "contacted" }),
    ...(typeFilter !== "all" && { request_type: typeFilter as "visit" | "consultation" })
  });

  const markContacted = useMarkRequestContacted();
  const deleteReq = useDeleteRequest();

  const handleMarkContacted = (id: number) => {
    markContacted.mutate(
      { id },
      {
        onSuccess: () => {
          toast({
            title: "Request Updated",
            description: "Marked as contacted successfully.",
          });
          queryClient.invalidateQueries({ queryKey: getListRequestsQueryKey() });
          queryClient.invalidateQueries({ queryKey: getGetRequestStatsQueryKey() });
        },
        onError: () => {
          toast({
            title: "Error",
            description: "Could not update request status.",
            variant: "destructive"
          });
        }
      }
    );
  };

  const handleDelete = (id: number) => {
    deleteReq.mutate(
      { id },
      {
        onSuccess: () => {
          toast({
            title: "Request Deleted",
            description: "The request has been removed.",
          });
          queryClient.invalidateQueries({ queryKey: getListRequestsQueryKey() });
          queryClient.invalidateQueries({ queryKey: getGetRequestStatsQueryKey() });
        },
        onError: () => {
          toast({
            title: "Error",
            description: "Could not delete request.",
            variant: "destructive"
          });
        }
      }
    );
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Client Inquiries</h2>
          <p className="text-muted-foreground mt-1">Manage visit requests and consultation messages from the bot</p>
        </div>
      </div>

      <Card className="p-4 shadow-sm border-border bg-card">
        <div className="flex flex-col md:flex-row gap-4 items-end md:items-center">
          <div className="w-full md:w-48 space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Status</Label>
            <Select value={statusFilter} onValueChange={(v: any) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="pending">Pending Only</SelectItem>
                <SelectItem value="contacted">Contacted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="w-full md:w-48 space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Inquiry Type</Label>
            <Select value={typeFilter} onValueChange={(v: any) => { setTypeFilter(v); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="visit">Property Visits</SelectItem>
                <SelectItem value="consultation">General Consultation</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <Button variant="outline" className="w-full md:w-auto" onClick={() => {
            setStatusFilter("all");
            setTypeFilter("all");
            setPage(1);
          }}>
            <Filter className="h-4 w-4 mr-2" /> Reset
          </Button>
        </div>
      </Card>

      <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 items-center">
                <Skeleton className="h-16 w-full" />
              </div>
            ))}
          </div>
        ) : requestsPage?.data && requestsPage.data.length > 0 ? (
          <>
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead>Client Details</TableHead>
                  <TableHead>Inquiry Info</TableHead>
                  <TableHead>Context</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requestsPage.data.map((req) => (
                  <TableRow key={req.id} className="group">
                    <TableCell>
                      <div className="font-medium" dir="rtl">{req.name}</div>
                      <div className="flex items-center text-sm text-muted-foreground mt-1">
                        <Phone className="h-3 w-3 mr-1" />
                        <span className="font-mono">{req.phone}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={req.request_type === 'visit' ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800' : 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'}>
                        {req.request_type.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {req.villa_code && req.villa_code !== 'None' ? (
                        <div className="flex flex-col gap-1">
                          <Link href={`/villas/${req.villa_code.replace('MV-', '')}`} className="font-mono text-sm text-primary hover:underline">
                            {req.villa_code}
                          </Link>
                          {req.villa_city && <span className="text-xs text-muted-foreground" dir="rtl">{req.villa_city}</span>}
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground italic">General</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {req.status === 'pending' ? (
                        <Badge className="bg-orange-100 text-orange-800 hover:bg-orange-100 border-orange-200 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-800">Pending</Badge>
                      ) : (
                        <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 border-emerald-200 dark:bg-emerald-900 dark:text-emerald-200 dark:border-emerald-800">Contacted</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {formatDate(req.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {req.status === 'pending' && (
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 border-emerald-200 dark:border-emerald-800 dark:hover:bg-emerald-950/50"
                            onClick={() => handleMarkContacted(req.id)}
                            disabled={markContacted.isPending}
                          >
                            <CheckCircle2 className="h-4 w-4 mr-1" /> Resolve
                          </Button>
                        )}
                        
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Inquiry</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete this request from {req.name}? This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction 
                                onClick={() => handleDelete(req.id)}
                                className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                              >
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            
            {/* Pagination Controls */}
            <div className="p-4 border-t flex items-center justify-between bg-muted/10">
              <div className="text-sm text-muted-foreground">
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, requestsPage.total)} of {requestsPage.total} inquiries
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setPage(p => p + 1)}
                  disabled={page * pageSize >= requestsPage.total}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="p-16 text-center flex flex-col items-center justify-center">
            <MessageSquare className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
            <h3 className="text-lg font-medium">No inquiries found</h3>
            <p className="text-muted-foreground mt-1 max-w-sm">
              We couldn't find any client requests matching your current filters.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
