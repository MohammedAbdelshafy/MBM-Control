import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { dataAccess } from '@/api/dataAccess';
import { useLang } from '@/lib/i18n';
import { useAuth } from '@/lib/AuthContext';
import { canAccess, isUnassignedRole } from '@/lib/roles';
import {
  LayoutDashboard, BarChart3, Building2, Truck, CreditCard, Award,
  Warehouse, Users, UsersRound, Car, UserCog, Menu, X, LogOut, Handshake, UserCheck, Inbox, FileText, Zap, Mic
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import PendingActivation from '@/components/PendingActivation';

const navItems = [
  { key: 'my_work', icon: LayoutDashboard, path: '/my-work', module: 'my_work' },
  { key: 'dashboard', icon: BarChart3, path: '/', module: 'dashboard' },
  { key: 'voice_agents', icon: Mic, path: '/voice-agents', module: 'dashboard', label: 'Voice Agents Studio' },
  { key: 'kpis', icon: BarChart3, path: '/kpis', module: 'kpis' },
  { key: 'buildings', icon: Building2, path: '/buildings', module: 'buildings' },
  { key: 'pickups', icon: Truck, path: '/pickups', module: 'pickups' },
  { key: 'todays_route', icon: Truck, path: '/todays-route', module: 'todays_route', label: 'todays_route' },
  { key: 'payments', icon: CreditCard, path: '/payments', module: 'payments' },
  { key: 'commissions', icon: Award, path: '/commissions', module: 'commissions' },
  { key: 'dealing_room', icon: Handshake, path: '/dealing-room', module: 'dealing_room' },
  { key: 'warehouse', icon: Warehouse, path: '/warehouse', module: 'warehouse' },
  { key: 'vehicles', icon: Car, path: '/vehicles', module: 'vehicles' },
  { key: 'sales_members', icon: UserCog, path: '/sales-members', module: 'sales_members' },
  { key: 'drivers', icon: UserCheck, path: '/drivers', module: 'drivers' },
  { key: 'new_requests', icon: Inbox, path: '/new-requests', module: 'new_requests' },
  { key: 'my_building', icon: Building2, path: '/my-building', module: 'my_building' },
  { key: 'users', icon: Users, path: '/users', module: 'users', label: 'team' },
  { key: 'reports', icon: FileText, path: '/reports', module: 'reports' },
  { key: 'customers', icon: UsersRound, path: '/customers', module: 'customers' },
  { key: 'mbm', icon: Zap, path: '/mbm', module: 'dashboard', label: 'MBM Dashboard' },
];

export default function AppLayout() {
  const { t, lang, setLang, isRTL } = useLang();
  const { user, logout } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [requestCount, setRequestCount] = useState(0);
  const role = user?.role;

  useEffect(() => {
    if (!role || !canAccess(role, 'new_requests')) return;
    dataAccess.buildings.list().then(all => {
      setRequestCount(all.filter(b => b.status === 'pickup_requested').length);
    }).catch(() => {});
  }, [role]);

  if (isUnassignedRole(role) && user?.invited_by_admin) {
    return <PendingActivation />;
  }

  const visibleNav = navItems.filter(item => canAccess(role, item.module));

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar - Desktop */}
      <aside className="hidden lg:flex flex-col w-64 glass-sidebar text-white shrink-0 z-20">
        <SidebarContent
          visibleNav={visibleNav}
          location={location}
          t={t}
          lang={lang}
          setLang={setLang}
          user={user}
          role={role}
          requestCount={requestCount}
          logout={logout}
        />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 right-0 w-72 glass-sidebar text-white flex flex-col rtl:right-auto rtl:left-0 ltr:right-auto ltr:left-0 shadow-2xl"
            style={isRTL ? { right: 0, left: 'auto' } : { left: 0, right: 'auto' }}>
            <div className="flex justify-end p-3">
              <button onClick={() => setMobileOpen(false)} className="text-white/70 hover:text-white">
                <X size={24} />
              </button>
            </div>
            <SidebarContent
              visibleNav={visibleNav}
              location={location}
              t={t}
              lang={lang}
              setLang={setLang}
              user={user}
              role={role}
              requestCount={requestCount}
              onNavClick={() => setMobileOpen(false)}
              logout={logout}
            />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 bg-white/70 backdrop-blur-md border-b flex items-center px-4 gap-3 shrink-0 z-10">
          <button className="lg:hidden text-navy" onClick={() => setMobileOpen(true)}>
            <Menu size={24} />
          </button>
          <div className="flex-1" />
          <button
            onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}
            className="text-xs font-bold px-2.5 py-1 rounded-md border border-border bg-muted/50 hover:bg-muted transition-colors"
          >
            {lang === 'ar' ? 'EN' : 'ع'}
          </button>
          <span className="text-sm text-muted-foreground hidden sm:block">
            {user?.full_name || user?.email}
          </span>
          <span className="text-xs bg-navy/10 text-navy px-2 py-0.5 rounded-full font-semibold">
            {t(role)}
          </span>
        </header>

        <main className="flex-1 overflow-auto p-4 md:p-6 relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3 }}
              className="h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

function SidebarContent({ visibleNav, location, t, lang, setLang, user, role, requestCount, onNavClick, logout }) {
  return (
    <>
      <div className="p-5 border-b border-white/10">
        <h1 className="text-2xl font-bold tracking-wide">dawrix</h1>
        <p className="text-xs text-white/60 mt-0.5">{t('app_subtitle')}</p>
      </div>

      <nav className="flex-1 overflow-auto py-2">
        {visibleNav.map(item => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.key}
              to={item.path}
              onClick={onNavClick}
              className={`flex items-center gap-3 px-5 py-2.5 text-sm font-medium transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]
                ${isActive
                  ? 'bg-white/15 text-white border-s-4 border-green shadow-sm'
                  : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`}
            >
              <Icon size={18} />
              {t(item.label || item.key)}
              {item.module === 'new_requests' && requestCount > 0 && (
                <span className="ms-auto bg-red-500 text-white text-xs font-bold rounded-full min-w-5 h-5 px-1.5 flex items-center justify-center">{requestCount}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/10 space-y-2">
        <button
          onClick={() => {
            logout();
          }}
          className="flex items-center gap-2 text-sm text-white/70 hover:text-white w-full px-2 py-1.5 rounded transition-colors"
        >
          <LogOut size={16} />
          {t('logout')}
        </button>
      </div>
    </>
  );
}