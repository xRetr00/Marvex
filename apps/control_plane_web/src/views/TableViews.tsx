import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";

type Row = Record<string, string | number | boolean | null>;

export function SafeTable({ title, rows, empty }: { title: string; rows: Row[]; empty: string }) {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {!rows.length ? <p className="text-sm text-muted-foreground">{empty}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  {keys.map((key) => <th className="px-2 py-2 font-medium" key={key}>{key}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr className="border-b border-border last:border-0" key={index}>
                    {keys.map((key) => <td className="px-2 py-2" key={key}>{format(row[key])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function format(value: Row[string]) {
  if (typeof value === "boolean") return <Badge tone={value ? "success" : "neutral"}>{String(value)}</Badge>;
  if (value === null || value === undefined) return <span className="text-muted-foreground">none</span>;
  return String(value);
}