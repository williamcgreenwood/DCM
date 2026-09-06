import { createFileRoute } from "@tanstack/react-router";
import { OperatorConsole } from "@/components/dcm/operator-console";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  return <OperatorConsole />;
}
