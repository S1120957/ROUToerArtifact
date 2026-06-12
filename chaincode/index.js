'use strict';
// Chaincode entrypoint. Deploy the source package with CommitWindow and the
// coordination package with Anchor. Both are exported here for convenience; in
// practice you package each contract separately for its channel.
const CommitWindow = require('./source/commitWindow');
const Anchor = require('./coordination/anchor');
module.exports.CommitWindow = CommitWindow;
module.exports.Anchor = Anchor;
module.exports.contracts = [CommitWindow, Anchor];
