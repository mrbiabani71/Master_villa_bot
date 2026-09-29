import { Link, useLocation } from "wouter";
import { LayoutDashboard, Home, MessageSquare, Menu } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [location] = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Villas", href: "/villas", icon: Home },
    { name: "Requests", href: "/requests", icon: MessageSquare },
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col md:flex-row">
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 border-b bg-sidebar text-sidebar-foreground">
        <h1 className="font-bold text-lg tracking-tight">Master Villa Bot</h1>
        <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="text-sidebar-foreground hover:bg-sidebar-accent">
          <Menu className="h-5 w-5" />
        </Button>
      </div>

      {/* Sidebar */}
      <aside className={`md:w-64 bg-sidebar text-sidebar-foreground flex flex-col transition-transform ${mobileMenuOpen ? "block" : "hidden md:flex"} fixed md:sticky top-0 h-screen z-50`}>
        <div className="p-6 border-b border-sidebar-border hidden md:block">
          <h1 className="font-bold text-xl tracking-tight text-white">Master Villa Bot</h1>
          <p className="text-xs text-sidebar-foreground/70 mt-1 uppercase tracking-wider font-semibold">Admin Portal</p>
        </div>
        
        <nav className="flex-1 py-6 px-4 space-y-2 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
            return (
              <Link key={item.name} href={item.href}>
                <span className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors cursor-pointer ${isActive ? "bg-sidebar-primary text-sidebar-primary-foreground font-medium" : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground text-sidebar-foreground/80"}`} onClick={() => setMobileMenuOpen(false)}>
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
