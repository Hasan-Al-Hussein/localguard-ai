"use client";

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useState, type ReactNode } from "react";

export function DataTable<T>({
  columns,
  data,
  getRowId,
  mobileRow,
  empty,
}: {
  columns: Array<ColumnDef<T>>;
  data: T[];
  getRowId?: (row: T) => string;
  mobileRow?: (row: T) => ReactNode;
  empty?: ReactNode;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  // TanStack Table intentionally returns a mutable table facade; React Compiler
  // skips this component while React Table owns its memoization lifecycle.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    getRowId,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  if (data.length === 0) return <>{empty}</>;

  return (
    <>
      <div className="panel hidden overflow-hidden md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="border-b border-border bg-surface-raised text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}
                      className="px-4 py-3"
                      key={header.id}
                      scope="col"
                    >
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button
                          className="icon-button inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 hover:bg-white hover:text-foreground"
                          onClick={header.column.getToggleSortingHandler()}
                          type="button"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === "asc" ? <ArrowUp aria-hidden className="size-3.5" /> : sorted === "desc" ? <ArrowDown aria-hidden className="size-3.5" /> : <ChevronsUpDown aria-hidden className="size-3.5" />}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border">
            {table.getRowModel().rows.map((row) => (
              <tr className="bg-surface transition-colors hover:bg-surface-muted" key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td className="px-4 py-3.5 align-middle" key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {mobileRow ? <div className="grid min-w-0 gap-3 md:hidden">{table.getRowModel().rows.map((row) => <div className="min-w-0 w-full" key={row.id}>{mobileRow(row.original)}</div>)}</div> : null}
    </>
  );
}
