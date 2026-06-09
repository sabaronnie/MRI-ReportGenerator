import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * App brand lockup: the Cervical MRI logo mark + wordmark. Single source of
 * truth — used in the header and the login page. Pass `showText={false}` for
 * the mark only.
 */
export function Brand({
  className,
  showText = true,
  size = 36,
}: {
  className?: string;
  showText?: boolean;
  size?: number;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <Image
        src="/logo.png"
        alt="Cervical MRI Reporting"
        width={size}
        height={size}
        priority
        className="shrink-0 object-contain"
        style={{ width: size, height: size }}
      />
      {showText ? (
        <span className="flex flex-col leading-none">
          <span className="font-serif text-[17px] font-semibold tracking-tight text-foreground">
            Cervical&nbsp;MRI
          </span>
          <span className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Reporting
          </span>
        </span>
      ) : null}
    </span>
  );
}
