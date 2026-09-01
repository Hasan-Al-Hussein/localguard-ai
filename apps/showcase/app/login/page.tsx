import type { Metadata } from "next";
import { PublicShowcaseLanding } from "../../components/public-showcase-landing";

export const metadata: Metadata = { title: "Explore" };

export default function LoginPage() {
  return <PublicShowcaseLanding />;
}
