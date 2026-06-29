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
      { name: 'Financials', type: 'PDF/Excel', mandatory: true },
      { name: 'Auditor Report', type: 'PDF', mandatory: true },
      { name: 'Company Input Sheet', type: 'Excel', mandatory: true }
    ],
    features: {
      hasPreviousYearComparison: false,
      hasCommonErrorCheck: true,
    },
    uiEngine: 'wizard',
    apiType: 'aoc4'
  }
};
