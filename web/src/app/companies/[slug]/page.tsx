import { redirect } from "next/navigation";

export default function LegacyCompanyRedirect() {
  redirect("/dashboard");
}
