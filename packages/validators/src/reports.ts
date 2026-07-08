import { z } from "zod";

export interface BaseReportSchemaMessages {
    medicineNameMin?: string;
    manufacturerMin?: string;
    descriptionMin?: string;
    pharmacyNameMin?: string;
    addressMin?: string;
    cityMin?: string;
    stateMin?: string;
}

export const getBaseReportFields = (messages?: BaseReportSchemaMessages) => {
    return {
        medicineName: z.string().min(2, messages?.medicineNameMin),
        manufacturer: z.string().min(2, messages?.manufacturerMin),
        description: z.string().min(20, messages?.descriptionMin),
        pharmacyName: z.string().min(2, messages?.pharmacyNameMin),
        address: z.string().min(5, messages?.addressMin),
        city: z.string().min(2, messages?.cityMin),
        state: z.string().min(2, messages?.stateMin),
        scannedBarcode: z.string().optional(),
    };
};

export const getBaseReportSchema = (messages?: BaseReportSchemaMessages) => {
    return z.object(getBaseReportFields(messages));
};
