export interface ABHALinkResponse {
    txnId: string;
}

export interface ABHAPrescription {
    id: string;
    title: string;
    issuedAt: string;
}

export interface ABHAVerificationData {
    medicineId: string;
    verificationResult: string;
    scannedAt: string;
}
