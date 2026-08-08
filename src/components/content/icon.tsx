import {
  Globe2, Landmark, Mountain, Scale, Building2, TrendingUp, Palette, Church, MessageSquare, Users,
  GraduationCap, Shield, Plane, UtensilsCrossed, Bird, CloudSun, Route, Star, Lightbulb, FlaskConical,
  Trophy, Flag, CalendarDays, Newspaper, Handshake, History, Sparkles, Image, BookOpen, Clock, MapPin,
  Medal, type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  Globe2, Landmark, Mountain, Scale, Building2, TrendingUp, Palette, Church, MessageSquare, Users,
  GraduationCap, Shield, Plane, UtensilsCrossed, Bird, CloudSun, Route, Star, Lightbulb, FlaskConical,
  Trophy, Flag, CalendarDays, Newspaper, Handshake, History, Sparkles, Image, BookOpen, Clock, MapPin, Medal,
};

export function Icon({ name, className }: { name?: string; className?: string }) {
  const Cmp = (name && ICONS[name]) || Sparkles;
  return <Cmp className={className} />;
}
