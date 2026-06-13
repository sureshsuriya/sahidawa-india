"use client";

import React from "react";
import { Search, Clock, Pin } from "lucide-react";

export interface HistoryItem {
    query: string;
    pinned: boolean;
    timestamp: number;
}

export interface SearchSuggestionsProps {
    /** The list of suggestion strings to display */
    suggestions: string[];
    /** The index of the currently keyboard-highlighted suggestion (-1 = none) */
    activeIndex: number;
    /** Called when a suggestion is clicked or selected via keyboard */
    onSelect: (value: string) => void;
    /** Whether the dropdown should be visible */
    visible: boolean;
    /** Whether suggestions are currently being loaded */
    isLoading?: boolean;
    /** An error message to display if loading suggestions failed */
    error?: string | null;
    /** Whether to show a "No results" message when there are no suggestions */
    noResults?: boolean;
    /** Called when the user clicks "Retry" after an error */
    onRetry?: () => void;
    /** Whether we are currently showing history instead of search suggestions */
    isHistory?: boolean;
    /** The list of search history items */
    historyItems?: HistoryItem[];
    /** Callback to pin/unpin a history item */
    onPinToggle?: (query: string) => void;
    /** Callback to clear all history */
    onClearHistory?: () => void;
}

/**
 * SearchSuggestions
 *
 * A purely presentational dropdown list that appears below a search input.
 *  * It renders loading, error, empty-state, or suggestion results
 * depending on the current search state.
 
 * Accessibility notes:
 *  - role="listbox" on the `<ul>` and role="option" on each `<li>`
 *  - aria-selected marks the active (keyboard-highlighted) item
 *  - id attributes are referenced by the parent input via aria-controls /
 *    aria-activedescendant (wired up in SearchBar)
 */
export default function SearchSuggestions({
    suggestions,
    activeIndex,
    onSelect,
    visible,
    isLoading = false,
    error = null,
    noResults = false,
    onRetry,
    isHistory = false,
    historyItems = [],
    onPinToggle,
    onClearHistory,
}: SearchSuggestionsProps) {
    if (!visible && !isLoading && !error && !noResults) {
        return null;
    }
    if (isHistory && (!historyItems || historyItems.length === 0)) {
        return null;
    }
    // Show error message if there was an error loading suggestions
    if (isLoading) {
        return (
            <div className="absolute top-full right-0 left-0 z-50 mt-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
                    Searching medicines...
                </div>
            </div>
        );
    }
    // Show error message if there was an error loading suggestions
    if (error) {
        return (
            <div className="absolute top-full right-0 left-0 z-50 mt-2 rounded-2xl border border-red-200 bg-white p-4 shadow-xl">
                <p className="mb-3 text-sm text-red-600">{error}</p>

                {onRetry && (
                    <button
                        type="button"
                        onClick={onRetry}
                        className="rounded-lg bg-red-500 px-3 py-2 text-sm text-white"
                    >
                        Retry
                    </button>
                )}
            </div>
        );
    }
    // Show "No results" message if there are no suggestions
    if (noResults) {
        return (
            <div className="absolute top-full right-0 left-0 z-50 mt-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
                <p className="text-sm text-slate-600">
                    No medicines found. Try another medicine name or batch number.
                </p>
            </div>
        );
    }

    return (
        <ul
            id="search-suggestions-listbox"
            role="listbox"
            aria-label="Search suggestions"
            className="animate-in fade-in slide-in-from-top-2 absolute top-full right-0 left-0 z-50 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60 duration-150"
        >
            {isHistory ? (
                <>
                    <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-5 py-2.5 text-[11px] font-bold tracking-wider text-slate-400 uppercase select-none">
                        <span>Recent Searches</span>
                        <button
                            type="button"
                            onMouseDown={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                onClearHistory?.();
                            }}
                            className="text-red-500 transition-colors hover:text-red-600 focus:outline-none"
                        >
                            Clear All
                        </button>
                    </div>
                    {historyItems.map((item, index) => {
                        const isActive = index === activeIndex;
                        return (
                            <li
                                key={`${item.query}-${index}`}
                                id={`search-suggestion-${index}`}
                                role="option"
                                aria-selected={isActive}
                                onMouseDown={(e) => {
                                    e.preventDefault();
                                    onSelect(item.query);
                                }}
                                className={`group flex cursor-pointer items-center justify-between px-5 py-3 text-sm font-medium transition-colors duration-100 ${
                                    isActive
                                        ? "bg-emerald-50 text-emerald-700"
                                        : "text-slate-700 hover:bg-slate-50"
                                } last:rounded-b-2xl`}
                            >
                                <div className="flex items-center gap-3 truncate">
                                    <Clock
                                        size={14}
                                        className={`shrink-0 ${isActive ? "text-emerald-500" : "text-slate-400"}`}
                                        aria-hidden="true"
                                    />
                                    <span className="truncate">{item.query}</span>
                                </div>
                                <button
                                    type="button"
                                    onMouseDown={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        onPinToggle?.(item.query);
                                    }}
                                    className={`ml-2 shrink-0 rounded p-1 transition-colors hover:bg-slate-200/50 ${
                                        item.pinned
                                            ? "text-emerald-500"
                                            : "text-slate-300 opacity-0 group-hover:opacity-100"
                                    }`}
                                    aria-label={
                                        item.pinned ? "Unpin search query" : "Pin search query"
                                    }
                                >
                                    <Pin
                                        size={14}
                                        className={item.pinned ? "fill-emerald-500" : ""}
                                    />
                                </button>
                            </li>
                        );
                    })}
                </>
            ) : (
                suggestions.map((suggestion, index) => {
                    const isActive = index === activeIndex;
                    return (
                        <li
                            key={`${suggestion}-${index}`}
                            id={`search-suggestion-${index}`}
                            role="option"
                            aria-selected={isActive}
                            onMouseDown={(e) => {
                                // Use mousedown instead of click to fire before the input's
                                // onBlur, which would otherwise close the list first.
                                e.preventDefault();
                                onSelect(suggestion);
                            }}
                            className={`flex cursor-pointer items-center gap-3 px-5 py-3 text-sm font-medium transition-colors duration-100 ${
                                isActive
                                    ? "bg-emerald-50 text-emerald-700"
                                    : "text-slate-700 hover:bg-slate-50"
                            } first:rounded-t-2xl last:rounded-b-2xl`}
                        >
                            <Search
                                size={14}
                                className={`shrink-0 ${isActive ? "text-emerald-500" : "text-slate-400"}`}
                                aria-hidden="true"
                            />
                            {/* Preserve exact string; parent can highlight matched portion if needed */}
                            <span className="truncate">{suggestion}</span>
                        </li>
                    );
                })
            )}
        </ul>
    );
}
