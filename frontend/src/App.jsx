import { Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout.jsx'
import AboutPage from './pages/AboutPage.jsx'
import AdminDashboardPage from './pages/AdminDashboardPage.jsx'
import ContactPage from './pages/ContactPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import HomePage from './pages/HomePage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import PickupRequestPage from './pages/PickupRequestPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import RequireAdmin from './components/RequireAdmin.jsx'
import RequireAuth from './components/RequireAuth.jsx'
import SellDevicePage from './pages/SellDevicePage.jsx'
import TrackDevicePage from './pages/TrackDevicePage.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="sell" element={<SellDevicePage />} />
        <Route path="track" element={<TrackDevicePage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="contact" element={<ContactPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route
          path="dashboard"
          element={(
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          )}
        />
        <Route
          path="dashboard/pickup"
          element={(
            <RequireAuth>
              <PickupRequestPage />
            </RequireAuth>
          )}
        />
        <Route
          path="admin"
          element={(
            <RequireAdmin>
              <AdminDashboardPage />
            </RequireAdmin>
          )}
        />
        <Route path="home" element={<Navigate replace to="/" />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
