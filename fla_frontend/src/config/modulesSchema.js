export const MODULES_SCHEMA = {
  fla: {
    id: 'fla',
    name: 'FLA Return',
    icon: 'FileText',
    description: 'Foreign Liabilities and Assets return automation',
    themeColor: 'indigo',
    uploadRequirements: [
      { name: 'Financials', type: 'PDF/MD', mandatory: true },
      { name: 'Audit / Board Report', type: 'PDF', mandatory: true },
      { name: 'ODI Details', type: 'PDF/MD', mandatory: true },
      { name: 'Input data from Company Details', type: 'Excel', mandatory: true },
      { name: 'List of Shareholders', type: 'Excel', mandatory: true },
      { name: 'Financials of Overseas Entities (if applicable)', type: 'PDF/Excel', mandatory: false }
    ],
    features: {
      hasPreviousYearComparison: true,
      hasCommonErrorCheck: false,
    },
    uiEngine: 'excel-viewer',
    apiType: 'fla'
  },
  aoc4: {
    id: 'aoc4',
    name: 'AOC 4 (MCA)',
    icon: 'ShieldAlert',
    description: 'Manage, extract, and review MCA AOC 4 financial statements',
    themeColor: 'emerald',
    uploadRequirements: [
      { name: 'Financials (Current Year)', type: 'PDF/Excel/MD', mandatory: true },
      { name: 'Auditor & Board Report', type: 'PDF/MD', mandatory: false },
      { name: 'Company Input / Validation Sheet', type: 'Excel', mandatory: false },
      { name: 'Prior Year Financials (Optional for Variance Reconciliation)', type: 'PDF/Excel/MD', mandatory: false }
    ],
    features: {
      hasPreviousYearComparison: true,
      hasCommonErrorCheck: true,
    },
    uiEngine: 'wizard',
    apiType: 'aoc4'
  }
};
