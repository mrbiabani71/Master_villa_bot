import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";
import { Layout } from "@/components/layout";

// Pages
import Dashboard from "@/pages/dashboard";
import VillasPage from "@/pages/villas/index";
import VillaDetail from "@/pages/villas/[id]";
import VillaNew from "@/pages/villas/new";
import VillaEdit from "@/pages/villas/edit";
import RequestsPage from "@/pages/requests/index";

const queryClient = new QueryClient();

function Router() {
  return (
    <Layout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/villas/new" component={VillaNew} />
        <Route path="/villas/:id/edit" component={VillaEdit} />
        <Route path="/villas/:id" component={VillaDetail} />
        <Route path="/villas" component={VillasPage} />
        <Route path="/requests" component={RequestsPage} />
        <Route component={NotFound} />
      </Switch>
    </Layout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
