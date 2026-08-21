import { lazy, Suspense } from 'react';
import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import UserNotRegisteredError from '@/components/UserNotRegisteredError';
import ScrollToTop from './components/ScrollToTop';
import ProtectedRoute from '@/components/ProtectedRoute';
import RoleRoute from '@/components/RoleRoute';
import { LangProvider } from '@/lib/i18n';

import Login from '@/pages/Login';
import AppLayout from '@/components/layout/AppLayout';

const Register = lazy(() => import('@/pages/Register'));
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'));
const ResetPassword = lazy(() => import('@/pages/ResetPassword'));
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const MyWorkDashboard = lazy(() => import('@/pages/MyWorkDashboard'));
const Kpis = lazy(() => import('@/pages/Kpis'));
const Buildings = lazy(() => import('@/pages/Buildings'));
const Pickups = lazy(() => import('@/pages/Pickups'));
const TodaysRoute = lazy(() => import('@/pages/TodaysRoute'));
const Payments = lazy(() => import('@/pages/Payments'));
const Commissions = lazy(() => import('@/pages/Commissions'));
const Warehouse = lazy(() => import('@/pages/Warehouse'));
const Vehicles = lazy(() => import('@/pages/Vehicles'));
const SalesMembers = lazy(() => import('@/pages/SalesMembers'));
const UserManagement = lazy(() => import('@/pages/UserManagement'));
const Customers = lazy(() => import('@/pages/Customers'));
const DealingRoom = lazy(() => import('@/pages/DealingRoom'));
const Drivers = lazy(() => import('@/pages/Drivers'));
const DoormanSignup = lazy(() => import('@/pages/DoormanSignup'));
const NewRequests = lazy(() => import('@/pages/NewRequests'));
const MyBuilding = lazy(() => import('@/pages/MyBuilding'));
const Reports = lazy(() => import('@/pages/Reports'));
const MissionControlDashboard = lazy(() => import('@/pages/MissionControlDashboard'));
const MissionDetail = lazy(() => import('@/pages/MissionDetail'));
const ChronicleSearch = lazy(() => import('@/pages/ChronicleSearch'));
const MBMDashboard = lazy(() => import('@/pages/MBMDashboard'));
const DemoLandingPage = lazy(() => import('@/pages/DemoLandingPage'));
const ClientHuntDashboard = lazy(() => import('@/pages/ClientHuntDashboard'));
const VoiceAgentsStudio = lazy(() => import('@/pages/VoiceAgentsStudio'));
const AffiliateAnalytics = lazy(() => import('@/pages/AffiliateAnalytics'));
const AutoDialer = lazy(() => import('@/pages/AutoDialer'));
const OfferPage = lazy(() => import('@/pages/OfferPage'));
const ShopifyStorefront = lazy(() => import('@/components/ShopifyStorefront'));
const AgencyDashboard = lazy(() => import('@/pages/AgencyDashboard'));
const MobileDialer = lazy(() => import('@/pages/MobileDialer'));
const DigitalServicesLeads = lazy(() => import('@/pages/DigitalServicesLeads'));

function PageLoader() {
  return <div className="flex items-center justify-center h-[50vh]"><div className="text-center"><div className="w-8 h-8 border-4 border-navy/20 border-t-navy rounded-full animate-spin mx-auto mb-3" /><p className="text-sm text-muted-foreground">Loading...</p></div></div>;
}

function ResponsiveDialerHome() {
  const isPhone = typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches;
  return isPhone ? <MobileDialer /> : <MBMDashboard />;
}

const AuthenticatedApp = () => {
  const { isLoadingAuth, isLoadingPublicSettings, authError, navigateToLogin } = useAuth();

  if (isLoadingPublicSettings || isLoadingAuth) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-navy/20 border-t-navy rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm text-muted-foreground font-heading">dawrix</p>
        </div>
      </div>
    );
  }

  if (authError) {
    if (authError.type === 'user_not_registered') {
      return <UserNotRegisteredError />;
    } else if (authError.type === 'auth_required') {
      navigateToLogin();
      return null;
    }
  }

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/bawab-signup" element={<Navigate to="/doorman-signup" replace />} />
        <Route path="/doorman-signup" element={<DoormanSignup />} />
        {/* Public Landing & Dashboards (No login required) */}
        <Route path="/" element={<ResponsiveDialerHome />} />
        <Route path="/demo" element={<DemoLandingPage />} />
        <Route path="/hunt" element={<ClientHuntDashboard />} />
        <Route path="/voice-agents" element={<VoiceAgentsStudio />} />
        <Route path="/voice-studio" element={<VoiceAgentsStudio />} />
        <Route path="/dialer" element={<ResponsiveDialerHome />} />
        <Route path="/auto-dialer" element={<ResponsiveDialerHome />} />
        <Route path="/dialer/mobile" element={<MobileDialer />} />
        <Route path="/mobile-dialer" element={<MobileDialer />} />
        <Route path="/digital-services" element={<DigitalServicesLeads />} />
        <Route path="/affiliates" element={<AffiliateAnalytics />} />
        <Route path="/mbm" element={<ResponsiveDialerHome />} />
        <Route path="/mbm-dashboard" element={<ResponsiveDialerHome />} />
        <Route path="/offer/:offerId" element={<OfferPage />} />
        <Route path="/store" element={<ShopifyStorefront />} />
        <Route path="/storefront" element={<ShopifyStorefront />} />
        <Route path="/agency" element={<AgencyDashboard />} />

        <Route element={<ProtectedRoute unauthenticatedElement={<Navigate to="/login" replace />} />}>
          <Route element={<AppLayout />}>
            <Route path="/my-work" element={<RoleRoute module="my_work"><MyWorkDashboard /></RoleRoute>} />
            <Route path="/dashboard" element={<RoleRoute module="dashboard"><Dashboard /></RoleRoute>} />
            <Route path="/kpis" element={<RoleRoute module="kpis"><Kpis /></RoleRoute>} />
            <Route path="/buildings" element={<RoleRoute module="buildings"><Buildings /></RoleRoute>} />
            <Route path="/pickups" element={<RoleRoute module="pickups"><Pickups /></RoleRoute>} />
            <Route path="/todays-route" element={<RoleRoute module="todays_route"><TodaysRoute /></RoleRoute>} />
            <Route path="/payments" element={<RoleRoute module="payments"><Payments /></RoleRoute>} />
            <Route path="/commissions" element={<RoleRoute module="commissions"><Commissions /></RoleRoute>} />
            <Route path="/warehouse" element={<RoleRoute module="warehouse"><Warehouse /></RoleRoute>} />
            <Route path="/vehicles" element={<RoleRoute module="vehicles"><Vehicles /></RoleRoute>} />
            <Route path="/sales-members" element={<RoleRoute module="sales_members"><SalesMembers /></RoleRoute>} />
            <Route path="/users" element={<RoleRoute module="users"><UserManagement /></RoleRoute>} />
            <Route path="/customers" element={<RoleRoute module="customers"><Customers /></RoleRoute>} />
            <Route path="/dealing-room" element={<RoleRoute module="dealing_room"><DealingRoom /></RoleRoute>} />
            <Route path="/drivers" element={<RoleRoute module="drivers"><Drivers /></RoleRoute>} />
            <Route path="/new-requests" element={<RoleRoute module="new_requests"><NewRequests /></RoleRoute>} />
            <Route path="/my-building" element={<RoleRoute module="my_building"><MyBuilding /></RoleRoute>} />
            <Route path="/reports" element={<RoleRoute module="reports"><Reports /></RoleRoute>} />
          </Route>
        </Route>
        {/* Mission Control (admin only) */}
        <Route path="/mission-control" element={<MissionControlDashboard />} />
        <Route path="/mission-control/:missionId" element={<MissionDetail />} />
        <Route path="/chronicle" element={<ChronicleSearch />} />

        <Route path="*" element={<PageNotFound />} />
      </Routes>
    </Suspense>
  );
};

function App() { return <LangProvider><AuthProvider><QueryClientProvider client={queryClientInstance}><ErrorBoundary><Router><ScrollToTop /><AuthenticatedApp /></Router><Toaster /></ErrorBoundary></QueryClientProvider></AuthProvider></LangProvider> }
export default App