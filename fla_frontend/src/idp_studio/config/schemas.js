export const IDP_SCHEMAS = {
    fla: {
        id: 'fla',
        name: 'FLA Return',
        fields: [
            { id: "paid_up_capital", label: "1. Paid up Capital" },
            { id: "reserves_and_surplus", label: "2. Reserves & Surplus" },
            { id: "net_worth", label: "3. Total Net Worth" },
            { id: "net_profit_before_tax", label: "4. Net Profit Before Tax" },
            { id: "turnover", label: "5. Total Turnover" },
            { id: "borrowings", label: "6. Total Borrowings" }
        ]
    },
    aoc4: {
        id: 'aoc4',
        name: 'AOC-4 (MCA)',
        fields: [
            { id: "revenue_from_operations", label: "I. Revenue from Operations" },
            { id: "other_income", label: "II. Other Income" },
            { id: "total_revenue", label: "III. Total Revenue (I + II)" },
            { id: "employee_benefit_expense", label: "IV(a). Employee Benefit Expenses" },
            { id: "finance_costs", label: "IV(b). Finance Costs" },
            { id: "depreciation", label: "IV(c). Depreciation & Amortization" },
            { id: "total_expenses", label: "IV. Total Expenses" },
            { id: "profit_before_tax", label: "V. Profit Before Tax" }
        ]
    },
    generic_invoice: {
        id: 'generic_invoice',
        name: 'Generic Invoice',
        fields: [
            { id: "invoice_number", label: "Invoice Number" },
            { id: "invoice_date", label: "Invoice Date" },
            { id: "vendor_name", label: "Vendor Name" },
            { id: "vendor_gstin", label: "Vendor GSTIN" },
            { id: "total_amount", label: "Total Amount" },
            { id: "tax_amount", label: "Tax Amount" },
            { id: "due_date", label: "Due Date" }
        ]
    }
};
