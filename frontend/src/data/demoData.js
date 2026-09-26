export const howItWorksSteps = [
  {
    number: '01',
    icon: 'clipboard',
    title: 'List your device',
    description: 'Tell us what you have, how old it is, and what condition it is in.',
  },
  {
    number: '02',
    icon: 'tag',
    title: 'Get estimated value',
    description: 'See a transparent demo estimate based on the details you share.',
  },
  {
    number: '03',
    icon: 'truck',
    title: 'Schedule pickup',
    description: 'Choose a convenient collection window and submit a pickup request.',
  },
  {
    number: '04',
    icon: 'search',
    title: 'Track processing',
    description: 'Follow your device with clear status updates from collection onward.',
  },
  {
    number: '05',
    icon: 'leaf',
    title: 'Refurbish or recycle',
    description: 'Devices are routed to the right outcome with a documented journey.',
  },
]

export const acceptedDevices = [
  { label: 'Smartphones', icon: 'smartphone', note: 'Android and iPhone' },
  { label: 'Laptops', icon: 'laptop', note: 'Notebooks and work laptops' },
  { label: 'Tablets', icon: 'tablet', note: 'Tablets and e-readers' },
  { label: 'Desktop computers', icon: 'desktop', note: 'Towers and all-in-ones' },
  { label: 'Monitors', icon: 'monitor', note: 'Displays and monitors' },
  { label: 'Televisions', icon: 'tv', note: 'TVs and related equipment' },
  { label: 'Printers', icon: 'printer', note: 'Printers and scanners' },
  { label: 'Accessories', icon: 'accessories', note: 'Keyboards, cables and more' },
  { label: 'Other electronics', icon: 'package', note: 'Tell us what you have' },
]

export const journeyStages = [
  { label: 'User submission', icon: 'clipboard' },
  { label: 'Pickup', icon: 'truck' },
  { label: 'Inspection', icon: 'search' },
  { label: 'Decision', icon: 'layers' },
]

/**
 * The seven characteristics the valuation service actually reads.
 *
 * Stage 4C correction: this list previously advertised "Accessories", which the
 * estimator never uses, and omitted Brand and the original purchase price, which
 * it does. It now mirrors the model's actual feature set in
 * `backend/app/services/valuation.py` so the page cannot mislead a user about
 * what moves the number.
 */
export const valuationFactors = [
  { icon: 'layers', title: 'Device category', description: 'The baseline category and model type.' },
  { icon: 'tag', title: 'Brand', description: 'The manufacturer of the device.' },
  { icon: 'calendar', title: 'Age', description: 'How long the device has been in use.' },
  { icon: 'spark', title: 'Condition', description: 'Overall wear, functionality and care.' },
  { icon: 'shield', title: 'Working status', description: 'Whether the device powers on and works.' },
  { icon: 'box', title: 'Physical damage', description: 'Visible wear that may affect reuse.' },
  { icon: 'wallet', title: 'Original purchase price', description: 'Optional. Used as the estimate baseline when given.' },
]

export const sampleTrackingSteps = [
  {
    title: 'Pickup requested',
    description: 'Your request is ready for collection.',
    date: '12 Jun 2026',
    state: 'complete',
  },
  {
    title: 'Device collected',
    description: 'Your device was collected by the SmartCycle team.',
    date: '14 Jun 2026',
    state: 'complete',
  },
  {
    title: 'Quality inspection',
    description: 'The device is being checked for functionality and condition.',
    date: 'In progress',
    state: 'current',
  },
  {
    title: 'Refurbishment / recycling',
    description: 'The best responsible outcome will be selected after inspection.',
    date: 'Pending',
    state: 'pending',
  },
  {
    title: 'Completed',
    description: 'The final outcome and next steps will be recorded here.',
    date: 'Pending',
    state: 'pending',
  },
]

// The user dashboard now reads real devices from the authenticated API
// (GET /api/users/me/devices), so no sample device list is needed there.

// The admin workspace now reads real records from the admin API, so the
// sample device list below is no longer used.

export const demoTrackingId = 'EW-2026-0001'
