require('dotenv').config();
const express = require('express');
const { TonClient, WalletContractV4, internal, toNano } = require('ton');
const { mnemonicToPrivateKey } = require('ton-crypto');
const app = express();
app.use(express.json());

const endpoint = 'https://toncenter.com/api/v2/jsonRPC';
const apiKey = 'df82b466369447773fbaf3c2e4ad82f6e37c0b53648ed2a934c1165041e6312d';
const client = new TonClient({ endpoint, apiKey });

app.post('/send', async (req, res) => {
    console.log("Получен запрос на /send:", req.body);
    try {
        const { to, amount, comment } = req.body;
        const mnemonic = 'addict runway paper tongue ozone relax brisk immune notice file raw drift dream book loan assault know shaft length moment spy correct unique plug'.split(' ');
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

app.listen(3000, () => console.log('TON API server running on port 3000')); 