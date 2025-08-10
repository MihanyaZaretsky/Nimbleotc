require('dotenv').config();
const express = require('express');
const { TonClient, WalletContractV4, internal, toNano } = require('ton');
const { mnemonicToPrivateKey } = require('ton-crypto');
const app = express();
app.use(express.json());

const endpoint = process.env.TONCENTER_ENDPOINT || 'https://toncenter.com/api/v2/jsonRPC';
const apiKey = process.env.TONCENTER_API_KEY;
const client = new TonClient({ endpoint, apiKey });

app.post('/send', async (req, res) => {
    console.log("Получен запрос на /send:", req.body);
    try {
        const { to, amount, comment } = req.body;
        const mnemonicEnv = process.env.WALLET_MNEMONIC;
        if (!mnemonicEnv) {
            return res.status(500).json({ ok: false, error: 'WALLET_MNEMONIC is not set' });
        }
        const mnemonic = mnemonicEnv.split(' ');
        const keyPair = await mnemonicToPrivateKey(mnemonic);

        const wallet = WalletContractV4.create({ workchain: 0, publicKey: keyPair.publicKey });
        const contract = client.open(wallet);

        const seqno = await contract.getSeqno();

        await contract.sendTransfer({
            seqno,
            secretKey: keyPair.secretKey,
            messages: [internal({
                value: toNano(amount),
                to,
                body: comment || ""
            })]
        });

        res.json({ ok: true, tx: { to, amount, comment } });
    } catch (e) {
        console.error("Ошибка при отправке TON:", e);
        res.status(500).json({ ok: false, error: e.toString() });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`TON API server running on port ${PORT}`)); 