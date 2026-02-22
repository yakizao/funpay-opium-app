import { useState, useMemo, useCallback, type ReactNode } from 'react';
import {
  Box, Table, TableHead, TableBody, TableRow, TableCell,
  Typography, TextField, InputAdornment, Chip, alpha, Skeleton,
  TableSortLabel,
} from '@mui/material';
import { Search as SearchIcon, FilterList as FilterIcon } from '@mui/icons-material';
import { TablePaper } from './TablePaper';

// ── Types ──────────────────────────────────────────────

export interface Column<T> {
  id: string;
  label: string;
  align?: 'left' | 'center' | 'right';
  width?: number | string;
  sortable?: boolean;
  /** Return a primitive for sorting; defaults to getValue */
  sortValue?: (row: T) => string | number;
  /** Return a string for text search; defaults to sortValue/getValue */
  searchValue?: (row: T) => string;
  /** Render the cell content */
  render: (row: T, index: number) => ReactNode;
}

export interface FilterGroup {
  label: string;
  value: string;
  options: { label: string; value: string; count?: number; color?: string }[];
  onChange: (value: string) => void;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  loading?: boolean;
  emptyMessage?: string;
  /** Filter groups shown as chip rows */
  filters?: FilterGroup[];
  /** Enable text search across searchValue/sortValue columns */
  searchable?: boolean;
  searchPlaceholder?: string;
  /** Extra content in the toolbar (right side) */
  toolbarExtra?: ReactNode;
  /** Default sort column id */
  defaultSortColumn?: string;
  defaultSortDirection?: 'asc' | 'desc';
  /** sx for the outer TablePaper */
  sx?: Record<string, unknown>;
  /** Skeleton row count while loading */
  skeletonRows?: number;
}

type SortDir = 'asc' | 'desc';

// ── Component ──────────────────────────────────────────

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyMessage = 'no data',
  filters,
  searchable = true,
  searchPlaceholder = 'search...',
  toolbarExtra,
  defaultSortColumn,
  defaultSortDirection = 'asc',
  sx,
  skeletonRows = 5,
}: DataTableProps<T>) {
  const [search, setSearch] = useState('');
  const [sortCol, setSortCol] = useState<string | null>(defaultSortColumn ?? null);
  const [sortDir, setSortDir] = useState<SortDir>(defaultSortDirection);

  const handleSort = useCallback((colId: string) => {
    if (sortCol === colId) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(colId);
      setSortDir('asc');
    }
  }, [sortCol]);

  // Search + sort
  const processed = useMemo(() => {
    let result = [...rows];

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(row =>
        columns.some(col => {
          const fn = col.searchValue ?? col.sortValue;
          if (!fn) return false;
          return String(fn(row)).toLowerCase().includes(q);
        }),
      );
    }

    // Sort
    if (sortCol) {
      const col = columns.find(c => c.id === sortCol);
      const fn = col?.sortValue;
      if (fn) {
        result.sort((a, b) => {
          const va = fn(a);
          const vb = fn(b);
          const cmp = typeof va === 'number' && typeof vb === 'number'
            ? va - vb
            : String(va).localeCompare(String(vb));
          return sortDir === 'asc' ? cmp : -cmp;
        });
      }
    }

    return result;
  }, [rows, search, sortCol, sortDir, columns]);

  const hasToolbar = searchable || (filters && filters.length > 0) || toolbarExtra;

  return (
    <TablePaper sx={sx}>
      {/* ── Toolbar ── */}
      {hasToolbar && (
        <Box sx={{
          px: 2, pt: 1.5, pb: 1,
          display: 'flex', flexDirection: 'column', gap: 1,
        }}>
          {/* Search + extra */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            {searchable && (
              <TextField
                size="small"
                placeholder={searchPlaceholder}
                value={search}
                onChange={e => setSearch(e.target.value)}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                      </InputAdornment>
                    ),
                  },
                }}
                sx={{
                  flex: 1, maxWidth: 360,
                  '& .MuiOutlinedInput-root': {
                    bgcolor: 'rgba(255,255,255,0.03)',
                    borderRadius: 2,
                    fontSize: 13,
                    height: 36,
                  },
                }}
              />
            )}
            {toolbarExtra && <Box sx={{ ml: 'auto', display: 'flex', gap: 1, alignItems: 'center' }}>{toolbarExtra}</Box>}
          </Box>

          {/* Filter chips */}
          {filters && filters.map(fg => (
            <Box key={fg.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              <FilterIcon sx={{ fontSize: 14, color: 'text.disabled', mr: 0.5 }} />
              {fg.options.map(opt => {
                const active = fg.value === opt.value;
                const chipColor = opt.color || '#8B5CF6';
                return (
                  <Chip
                    key={opt.value}
                    size="small"
                    label={opt.count !== undefined ? `${opt.label} (${opt.count})` : opt.label}
                    onClick={() => fg.onChange(opt.value)}
                    sx={{
                      fontSize: '0.72rem',
                      fontWeight: active ? 700 : 500,
                      bgcolor: active ? alpha(chipColor, 0.18) : 'rgba(255,255,255,0.04)',
                      color: active ? chipColor : 'text.secondary',
                      border: active ? `1px solid ${alpha(chipColor, 0.3)}` : '1px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                      '&:hover': {
                        bgcolor: active ? alpha(chipColor, 0.22) : 'rgba(255,255,255,0.08)',
                      },
                    }}
                  />
                );
              })}
            </Box>
          ))}
        </Box>
      )}

      {/* ── Table ── */}
      <Table size="small">
        <TableHead>
          <TableRow sx={{
            '& .MuiTableCell-head': {
              fontWeight: 700,
              fontSize: '0.7rem',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'text.secondary',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              py: 1.2,
              whiteSpace: 'nowrap',
            },
          }}>
            {columns.map(col => (
              <TableCell key={col.id} align={col.align} sx={{ width: col.width }}>
                {col.sortable ? (
                  <TableSortLabel
                    active={sortCol === col.id}
                    direction={sortCol === col.id ? sortDir : 'asc'}
                    onClick={() => handleSort(col.id)}
                    sx={{
                      '&.MuiTableSortLabel-root': { color: 'text.secondary' },
                      '&.MuiTableSortLabel-root:hover': { color: 'text.primary' },
                      '&.Mui-active': { color: 'text.primary' },
                      '& .MuiTableSortLabel-icon': { fontSize: 14 },
                    }}
                  >
                    {col.label}
                  </TableSortLabel>
                ) : col.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {loading ? (
            [...Array(skeletonRows)].map((_, i) => (
              <TableRow key={`sk-${i}`}>
                {columns.map(col => (
                  <TableCell key={col.id}><Skeleton sx={{ bgcolor: 'rgba(255,255,255,0.04)' }} /></TableCell>
                ))}
              </TableRow>
            ))
          ) : processed.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
                <Typography variant="body2">{search ? 'no results found' : emptyMessage}</Typography>
              </TableCell>
            </TableRow>
          ) : (
            processed.map((row, i) => (
              <TableRow
                key={rowKey(row, i)}
                sx={{
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
                  '& .MuiTableCell-root': {
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    py: 1.2,
                    fontSize: '0.82rem',
                  },
                }}
              >
                {columns.map(col => (
                  <TableCell key={col.id} align={col.align}>{col.render(row, i)}</TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Footer count */}
      {!loading && rows.length > 0 && (
        <Box sx={{ px: 2, py: 1, borderTop: '1px solid rgba(255,255,255,0.04)', display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="caption" color="text.disabled">
            {processed.length === rows.length
              ? `${rows.length} rows`
              : `${processed.length} of ${rows.length} rows`}
          </Typography>
        </Box>
      )}
    </TablePaper>
  );
}
