import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Accounts } from "@/routes/Accounts";
import { Categories } from "@/routes/Categories";
import { Dashboard } from "@/routes/Dashboard";
import { Imports } from "@/routes/Imports";
import { ReviewQueue } from "@/routes/ReviewQueue";
import { Rules } from "@/routes/Rules";
import { Transactions } from "@/routes/Transactions";
import { Envelopes } from "@/routes/Envelopes";
import { Subscriptions } from "@/routes/Subscriptions";
import { Holdings } from "@/routes/Holdings";
import { Settings } from "@/routes/Settings";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="imports" element={<Imports />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="categories" element={<Categories />} />
        <Route path="rules" element={<Rules />} />
        <Route path="subscriptions" element={<Subscriptions />} />
        <Route path="envelopes" element={<Envelopes />} />
        <Route path="holdings" element={<Holdings />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
