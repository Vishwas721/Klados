import { Lead } from "@/lib/types";
import { CategoryBadge } from "./CategoryBadge";
import { PerformanceBadges } from "./PerformanceBadges";
import { TechStackTags } from "./TechStackTags";
import { LeadRowActions } from "./LeadRowActions";

const COLUMNS = ["Business Name", "Phone Number", "Category", "Performance", "Tech Stack", "Actions"];

interface LeadsTableProps {
  leads: Lead[];
  onWhatsAppSent: (id: string) => Promise<void>;
  onOptOut: (id: string) => Promise<void>;
}

export function LeadsTable({ leads, onWhatsAppSent, onOptOut }: LeadsTableProps) {
  if (leads.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-white py-16 text-center text-sm text-gray-400">
        No leads match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {COLUMNS.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {leads.map((lead) => (
            <tr key={lead.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <div className="text-sm font-medium text-gray-900">{lead.business_name}</div>
                {lead.website_url && (
                  <a
                    href={lead.website_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    {lead.website_url}
                  </a>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">{lead.phone_number || "—"}</td>
              <td className="px-4 py-3">
                <CategoryBadge category={lead.category} />
              </td>
              <td className="px-4 py-3">
                <PerformanceBadges ttfbMs={lead.ttfb_ms} domLoadMs={lead.dom_load_time_ms} />
              </td>
              <td className="px-4 py-3">
                <TechStackTags tech={lead.detected_tech} />
              </td>
              <td className="px-4 py-3">
                <LeadRowActions lead={lead} onWhatsAppSent={onWhatsAppSent} onOptOut={onOptOut} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
