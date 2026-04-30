import Decimal from "decimal.js";

export function formatINR(value: string | number, withSymbol = true): string {
  const d = new Decimal(value || 0);
  // Indian grouping: 1,23,45,678.90
  const [whole, frac = ""] = d.abs().toFixed(2).split(".");
  let formatted: string;
  if (whole.length <= 3) {
    formatted = whole;
  } else {
    const last3 = whole.slice(-3);
    const rest = whole.slice(0, -3);
    const grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    formatted = `${grouped},${last3}`;
  }
  const sign = d.isNegative() ? "-" : "";
  return `${sign}${withSymbol ? "₹" : ""}${formatted}.${frac}`;
}
