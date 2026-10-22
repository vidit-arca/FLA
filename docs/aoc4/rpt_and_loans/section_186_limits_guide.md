# Understanding Loan & Investment Limits (Section 186)

This guide explains how our automation system determines whether a company has stayed within its legal limits for making loans and investments, and how it automatically flags when special shareholder approvals are required.

## The Rule (Section 186 of the Companies Act)
When a company gives loans, provides guarantees, or makes investments, the government sets a maximum limit on how much they can give without needing special permission from their shareholders. 

To determine this maximum limit, the system looks at the company's financial health by calculating two specific limits based on the company's financial figures:

*   **Limit A:** 60% of their (Paid-up Capital + Free Reserves + Securities Premium)
*   **Limit B:** 100% of their (Free Reserves + Securities Premium)

The law allows the company to use **whichever limit is higher**.

---

## How the System Automates This Check

Whenever the system detects that a company has given out loans or made investments, it performs the following automated steps:

### 1. Calculates the Maximum Allowed Limit
The system automatically extracts the Paid-up Capital, Free Reserves, and Securities Premium from the company's financial statements. It calculates **Limit A** and **Limit B**, and picks the highest number as the final "Maximum Allowed Limit".

### 2. Adds Up Total Actual Transactions
The system then adds up all the actual Loans, Investments, and Guarantees the company gave out during the financial year.

### 3. The Final Comparison
Finally, the system compares the **Total Actual Transactions** against the **Maximum Allowed Limit**.

> [!TIP]
> **Scenario 1: The company stayed WITHIN the limit**
> *   **What the system does:** It marks the check as "Passed".
> *   **Action Required:** The system automatically outputs **"Yes"** for the Board Report requirement (meaning they just need to mention it in the Board Report) and indicates that no further action is needed.

> [!WARNING]
> **Scenario 2: The company EXCEEDED the limit**
> *   **What the system does:** It flags the transaction for a **"Manual"** check.
> *   **Action Required:** Because the limit was exceeded, the law requires the company to get prior approval from shareholders via a Special Resolution. The system warns the compliance team to **"check SR" (Check Special Resolution)** and ensures this is disclosed in the **MGT-8** filing.

---

## A Simple Example

Imagine a company with the following financials:
*   **Paid-up Capital:** ₹100
*   **Free Reserves:** ₹50
*   **Securities Premium:** ₹50

**Step 1: The system calculates the limits:**
*   **Limit A (60% Rule):** 60% of (100 + 50 + 50) = **₹120**
*   **Limit B (100% Rule):** 100% of (50 + 50) = **₹100**
*   **Maximum Allowed Limit:** The higher number is **₹120**.

**Step 2: The system checks the actual transactions:**
*   Let's say the company gave out **₹100** in total loans.

**Step 3: The Result:**
Since the actual loans (₹100) are less than the maximum limit (₹120), the system considers this **Within Limits**. It passes the check automatically and confirms that no Special Resolution or MGT-8 disclosure is required for exceeding limits.
