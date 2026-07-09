export interface VerifiedPharmacy {
    id?: string;
    name: string;
    address: string;
    lat: number;
    lng: number;
    distance: string;
    phone_number: string | null;
    is_verified: boolean;
    district: string | null;
    state: string | null;
    updated_at?: string;
    is_active?: boolean;
    deleted_at?: string | null;
    /** OSM `opening_hours` syntax, e.g. "Mo-Sa 09:00-21:00". Null/absent = unavailable. */
    operating_hours?: string | null;
    /** IANA timezone for evaluating operating_hours, e.g. "Asia/Kolkata". */
    timezone?: string | null;
}
