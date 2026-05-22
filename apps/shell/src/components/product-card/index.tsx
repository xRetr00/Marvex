import { cn } from "@/lib/utils";
import SmoothButton from "@/components/smooth-button";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

export interface ProductCardProps {
  badge?: string;
  className?: string;
  currency?: string;
  image: string;
  onAddToCart?: () => void;
  onWishlist?: () => void;
  originalPrice?: number;
  price: number;
  rating?: number;
  title: string;
}

const SPRING = { type: "spring" as const, duration: 0.25, bounce: 0.1 };
const SPRING_BOUNCY = { type: "spring" as const, duration: 0.3, bounce: 0.2 };
const STAR_PATH = "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.562.562 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z";

function RatingStars({ rating, title }: { rating: number; title: string }) {
  const fullStars = Math.floor(rating);
  const hasHalf = rating - fullStars >= 0.25 && rating - fullStars < 0.75;
  const roundedUp = rating - fullStars >= 0.75;
  return (
    <div aria-label={`${rating} out of 5 stars`} className="flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => {
        const isFilled = i < fullStars || (roundedUp && i === fullStars);
        return (
          <svg key={`star-${title}-${i}`} className={cn("h-3.5 w-3.5", isFilled ? "text-amber-400" : "text-muted-foreground/30")} fill={isFilled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={isFilled ? 0 : 1.5} viewBox="0 0 24 24">
            <path d={STAR_PATH} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        );
      })}
      <span className="ml-1 font-medium text-muted-foreground text-xs">{rating}</span>
    </div>
  );
}

export default function ProductCard({ image, title, price, originalPrice, currency = "$", rating, badge, onAddToCart, onWishlist, className }: ProductCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const [isAdded, setIsAdded] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [isHoverDevice, setIsHoverDevice] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(hover: hover) and (pointer: fine)");
    setIsHoverDevice(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsHoverDevice(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const handleAddToCart = () => { setIsAdded(true); onAddToCart?.(); setTimeout(() => setIsAdded(false), 2000); };
  const handleWishlist = () => { setIsWishlisted((prev) => !prev); onWishlist?.(); };
  const hasDiscount = originalPrice !== undefined && originalPrice > price;
  const discountPercent = hasDiscount ? Math.round(((originalPrice - price) / originalPrice) * 100) : 0;

  return (
    <motion.div
      aria-label={`${title} - ${currency}${price}`}
      className={cn("group relative flex w-full flex-col overflow-hidden rounded-2xl border bg-card shadow-sm", isHoverDevice && "hover:shadow-xl", className)}
      initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, transform: "translateY(20px) scale(0.97)" }}
      role="article"
      transition={shouldReduceMotion ? { duration: 0 } : SPRING}
      viewport={{ once: true, margin: "-50px" }}
      whileInView={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, transform: "translateY(0px) scale(1)" }}
    >
      <div className="relative aspect-square overflow-hidden bg-muted">
        <img alt={title} className={cn("h-full w-full object-cover", !shouldReduceMotion && "transition-transform duration-500", isHoverDevice && !shouldReduceMotion && "group-hover:scale-105")} src={image} />
        {badge && (
          <motion.span animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, transform: "scale(1)" }}
            className={cn("absolute top-3 left-3 rounded-full px-2.5 py-1 font-semibold text-xs shadow-sm", badge.toLowerCase() === "sale" ? "bg-red-500 text-white" : badge.toLowerCase() === "new" ? "bg-emerald-500 text-white" : "bg-primary text-primary-foreground")}
            initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, transform: "scale(0.6)" }} role="status" transition={shouldReduceMotion ? { duration: 0 } : SPRING_BOUNCY}>
            {badge}
          </motion.span>
        )}
        <motion.button aria-label={isWishlisted ? `Remove ${title} from wishlist` : `Add ${title} to wishlist`}
          className={cn("absolute top-3 right-3 flex h-8 w-8 items-center justify-center rounded-full bg-background/80 backdrop-blur-sm", isHoverDevice ? "opacity-0 group-hover:opacity-100" : "opacity-100")}
          onClick={handleWishlist} type="button">
          <svg className={cn("h-4 w-4", isWishlisted ? "text-red-500" : "text-foreground")} fill={isWishlisted ? "currentColor" : "none"} stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </motion.button>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="line-clamp-1 font-semibold text-foreground text-sm tracking-tight">{title}</h3>
        {rating !== undefined && <RatingStars rating={rating} title={title} />}
        <div className="flex items-baseline gap-2">
          <span className="font-bold text-foreground text-xl tracking-tight">{currency}{price}</span>
          {hasDiscount && (
            <>
              <span className="text-muted-foreground text-sm line-through">{currency}{originalPrice}</span>
              <span className="rounded-md bg-red-50 px-1.5 py-0.5 font-semibold text-red-600 text-xs">-{discountPercent}%</span>
            </>
          )}
        </div>
        <div className="mt-auto pt-2">
          <SmoothButton aria-label={`Add ${title} to cart`} className={cn("w-full gap-2", isAdded && "bg-emerald-600 text-white hover:bg-emerald-600")} disabled={isAdded} onClick={handleAddToCart} size="default" variant="candy">
            <AnimatePresence initial={false} mode="wait">
              {isAdded ? (
                <motion.span animate={{ opacity: 1 }} exit={{ opacity: 0 }} initial={{ opacity: 0 }} key="added">Added</motion.span>
              ) : (
                <motion.span animate={{ opacity: 1 }} exit={{ opacity: 0 }} initial={{ opacity: 0 }} key="cart">Add to Cart</motion.span>
              )}
            </AnimatePresence>
          </SmoothButton>
        </div>
      </div>
    </motion.div>
  );
}
