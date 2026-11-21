import { getServiceStatus } from "@/lib/health";
import { cn } from "@/lib/utils";

/** FR-2.19: whether each service answers GET /health. Text says up/down, so it doesn't rely on colour alone. */
export async function StatusLine() {
  const services = await getServiceStatus();
  return (
    <ul aria-label="Service status" className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
      {services.map(({ name, up }) => (
        <li key={name} className="flex items-center gap-1.5">
          <span aria-hidden className={cn("size-2 rounded-full", up ? "bg-leaf" : "bg-destructive")} />
          <span>
            {name} <span className={up ? "text-muted-foreground" : "font-bold text-destructive"}>{up ? "up" : "down"}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
